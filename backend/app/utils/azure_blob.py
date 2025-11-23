# app/utils/azure_blob.py
from typing import List, Dict, Union
import anyio, asyncio
from azure.storage.blob.aio import BlobServiceClient, ContainerClient
from azure.storage.blob import generate_container_sas, ContainerSasPermissions
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from app.config import config
from datetime import datetime, timedelta
# from app.utils.blob_to_qdrant import process_blob_and_store_vectors

# Config
AZURE_STORAGE_ACCOUNT = config.AZURE_STORAGE_ACCOUNT
AZURE_STORAGE_KEY = config.AZURE_STORAGE_KEY
AZURE_STORAGE_CONTAINER = config.AZURE_STORAGE_CONTAINER or "scopingbot"

if not AZURE_STORAGE_ACCOUNT or not AZURE_STORAGE_KEY:
    raise RuntimeError("Azure Storage credentials missing in config.py/.env")

_blob_service: BlobServiceClient = BlobServiceClient(
    account_url=f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net",
    credential=AZURE_STORAGE_KEY,
)

container: ContainerClient = _blob_service.get_container_client(AZURE_STORAGE_CONTAINER)

# Ensure container exists
async def init_container():
    try:
        await container.create_container()
    except ResourceExistsError:
        pass


# Helpers
def _normalize_path(blob_name: str, base: str) -> str:
    blob_name = blob_name.strip("/")
    base = base.strip("/")
    if base and blob_name.startswith(base + "/"):
        blob_name = blob_name[len(base) + 1:]
    return f"{base}/{blob_name}" if base else blob_name


# Upload
async def upload_bytes(
    data: Union[bytes, bytearray],
    blob_name: str,
    base: str = "",
    overwrite: bool = True
) -> str:
    path = _normalize_path(blob_name, base)
    blob = container.get_blob_client(path)

    for attempt in range(3):
        try:
            await blob.upload_blob(data, overwrite=overwrite)
            return path
        except Exception as e:
            # Azure may briefly reject upload if the blob was just deleted
            if attempt < 2:
                print(f" Upload retry {attempt+1}/3 for {path}: {e}")
                await anyio.sleep(1.0)
                continue
            print(f" Upload failed permanently for {path}: {e}")
            raise


async def upload_file(path: str, blob_name: str, base: str = "") -> str:
    with open(path, "rb") as f:
        data = f.read()
    return await upload_bytes(data, blob_name, base=base)


# Download
async def download_bytes(blob_name: str, base: str = "", timeout: int = 300) -> bytes:
    """
    Download a blob as bytes.

    Args:
        blob_name: Name/path of the blob
        base: Base path prefix
        timeout: Timeout in seconds (default: 300 = 5 minutes for large files like PPTs)

    Returns:
        Blob content as bytes
    """
    path = _normalize_path(blob_name, base)
    blob = container.get_blob_client(path)
    stream = await blob.download_blob(timeout=timeout)
    return await stream.readall()

async def download_text(blob_name: str, base: str = "", encoding: str = "utf-8") -> str:
    raw = await download_bytes(blob_name, base)
    return raw.decode(encoding, errors="ignore")


# Listing
async def list_bases() -> List[Dict]:
    return [
        {"name": "projects", "path": "projects", "is_folder": True},
        {"name": "knowledge_base", "path": "knowledge_base", "is_folder": True},
    ]

async def build_tree(base: str, prefix: str = "") -> List[Dict]:
    path = _normalize_path(prefix, base)
    if path and not path.endswith("/"):
        path += "/"

    items: List[Dict] = []
    seen_folders = set()

    async for blob in container.list_blobs(name_starts_with=path):
        relative = blob.name[len(path):]
        if not relative:
            continue

        parts = relative.split("/", 1)
        if len(parts) == 1:
            items.append({
                "name": parts[0],
                "path": blob.name,
                "is_folder": False,
                "size": blob.size,
            })
        else:
            folder_name = parts[0]
            if folder_name not in seen_folders:
                seen_folders.add(folder_name)
                children = await build_tree(base, (prefix + "/" + folder_name).strip("/"))
                items.append({
                    "name": folder_name,
                    "path": f"{path}{folder_name}",
                    "is_folder": True,
                    "children": children,
                })

    return items

async def explorer(base: str) -> Dict:
    return {"base": base, "children": await build_tree(base)}


# DELETE

async def delete_blob(blob_name: str, base: str = "") -> bool:
    """Delete a single blob safely."""
    path = _normalize_path(blob_name, base)
    blob = container.get_blob_client(path)
    try:
        await blob.delete_blob()
        return True
    except ResourceNotFoundError:
        return False
    except Exception as e:
        return False

async def delete_folder(prefix: str, base: str = "") -> List[str]:
    """
    Delete all blobs under a folder prefix like 'projects/<id>/' concurrently for speed.
    This version correctly uses blob clients (no NoneType await issue).
    """
    path = _normalize_path(prefix, base)
    if not path.endswith("/"):
        path += "/"

    deleted = []

    async def _delete_single(blob_name: str):
        try:
            blob_client = container.get_blob_client(blob_name)
            await blob_client.delete_blob()
            deleted.append(blob_name)
        except ResourceNotFoundError:
            pass
        except Exception as e:
            print(f" Failed to delete {blob_name}: {e}")

    try:
        tasks = []
        async for blob in container.list_blobs(name_starts_with=path):
            tasks.append(_delete_single(blob.name))
        if tasks:
            await asyncio.gather(*tasks)
    except Exception as e:
        print(f"delete_folder failed for {path}: {e}")
    return deleted



async def delete_blob_async(blob_path: str) -> bool:
    """
    Delete only the specific blob provided.
    Never recursively delete a folder unless explicitly called by delete_folder().
    """
    try:
        # Prevent accidental folder deletions
        if blob_path.endswith("/") or blob_path.count(".") == 0:
            print(f" Skipping recursive folder deletion for safety: {blob_path}")
            return False

        return await delete_blob(blob_path)
    except Exception as e:
        print(f" Failed async delete for {blob_path}: {e}")
        return False



def delete_blob_sync(blob_path: str):
    """
    Full synchronous safe wrapper for delete_blob_async().
    Works in or outside an existing asyncio event loop.
    Used by cleanup tasks in non-async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
        future = asyncio.run_coroutine_threadsafe(delete_blob_async(blob_path), loop)
        return future.result()
    except RuntimeError:
        return asyncio.run(delete_blob_async(blob_path))
    except Exception as e:
        print(f" delete_blob_sync failed for {blob_path}: {e}")
        return False


def safe_delete_blob(blob_path: str):
    """
    Fire-and-forget blob delete — now protected against folder wipes.
    """
    try:
        # Prevent unsafe deletions of project folders
        if blob_path.endswith("/") or blob_path.count(".") == 0:
            print(f" Ignoring unsafe folder delete request: {blob_path}")
            return

        loop = asyncio.get_running_loop()
        loop.create_task(delete_blob_async(blob_path))
    except RuntimeError:
        asyncio.run(delete_blob_async(blob_path))


# Existence & URL
async def blob_exists(blob_name: str, base: str = "") -> bool:
    path = _normalize_path(blob_name, base)
    blob = container.get_blob_client(path)
    return await blob.exists()

def get_blob_url(blob_name: str, base: str = "") -> str:
    path = _normalize_path(blob_name, base)
    return (
        f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/"
        f"{AZURE_STORAGE_CONTAINER}/{path}"
    )

def generate_sas_url(expiry_hours: int = 1) -> str:
    sas_token = generate_container_sas(
        account_name=AZURE_STORAGE_ACCOUNT,
        container_name=AZURE_STORAGE_CONTAINER,
        account_key=AZURE_STORAGE_KEY,
        permission=ContainerSasPermissions(
            read=True, list=True, delete=True, write=True, add=True, create=True
        ),
        expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
    )
    return f"https://{AZURE_STORAGE_ACCOUNT}.blob.core.windows.net/{AZURE_STORAGE_CONTAINER}?{sas_token}"

# setting up the ETL from blob to qdrant

# def upload_blob(file):
#     # existing blob upload logic
#     blob_client.upload_blob(file)
#     logger.info(f"Uploaded {file.filename} to Azure Blob.")

#     # Trigger ETL → Qdrant
#     process_blob_and_store_vectors(file.filename)