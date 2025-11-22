// BlobDashboard.jsx
import { useEffect, useState } from "react";
import { useBlobs } from "../contexts/BlobContext";
import {
  Upload,
  Folder,
  Trash2,
  RefreshCcw,
  File as FileIcon,
  ChevronRight,
  ChevronDown,
  Eye,
} from "lucide-react";

// Folder Node (recursive)

function FolderNode({ node, base, deleteFile, deleteFolder, previewFile }) {
  const [expanded, setExpanded] = useState(false);

  const toggleExpand = () => {
    if (node.is_folder) setExpanded((x) => !x);
  };

  const onDeleteFolder = async (e) => {
    e.stopPropagation();
    await deleteFolder(node.path, base);
  };

  const onDeleteFile = async (e) => {
    e.stopPropagation();
    await deleteFile(node.path, base);
  };

  const onPreviewFile = async (e) => {
    e.stopPropagation();
    await previewFile(node.path, base);
  };

  return (
    <li className="pl-4">
      <div
        className={`flex items-center justify-between ${
          node.is_folder ? "cursor-pointer" : ""
        }`}
        onClick={toggleExpand}
      >
        <div className="flex items-center gap-2">
          {node.is_folder ? (
            <>
              {expanded ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronRight className="w-4 h-4 text-gray-500" />
              )}
              <Folder className="w-4 h-4 text-gray-500" />
              <span>{node.name}</span>
            </>
          ) : (
            <>
              <FileIcon className="w-4 h-4 text-gray-500" />
              <span>{node.name}</span>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          {!node.is_folder && (
            <button
              onClick={onPreviewFile}
              className="text-sm text-blue-500 hover:underline flex items-center gap-1"
            >
              <Eye className="w-4 h-4" /> Preview
            </button>
          )}
          {node.is_folder ? (
            <button
              onClick={onDeleteFolder}
              className="text-sm text-red-500 hover:underline flex items-center gap-1"
            >
              <Trash2 className="w-4 h-4" /> Delete Folder
            </button>
          ) : (
            <button
              onClick={onDeleteFile}
              className="text-sm text-red-500 hover:underline flex items-center gap-1"
            >
              <Trash2 className="w-4 h-4" /> Delete
            </button>
          )}
        </div>
      </div>

      {expanded && node.is_folder && node.children?.length > 0 && (
        <ul className="pl-6 mt-1 space-y-1">
          {node.children.map((child) => (
            <FolderNode
              key={child.path}
              node={child}
              base={base}
              deleteFile={deleteFile}
              deleteFolder={deleteFolder}
              previewFile={previewFile}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

// Main Dashboard
export default function BlobDashboard() {
  const {
    tree,
    loadExplorer,
    uploadFile,
    uploadFolder,
    deleteFile,
    deleteFolder,
    previewFile,
    loading,
  } = useBlobs();

  const [activeBase, setActiveBase] = useState("knowledge_base");

  useEffect(() => {
    loadExplorer(activeBase);
  }, [activeBase, loadExplorer]);


  const onUploadFile = async (e) => {
    const f = e.target.files[0];
    if (f) {
      await uploadFile(f, "", activeBase);
      await loadExplorer(activeBase);
    }
  };

  const onUploadFolder = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      await uploadFolder(files, "", activeBase);
      await loadExplorer(activeBase);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-extrabold text-gray-800 dark:text-gray-100">
          Blob Storage Explorer
        </h1>
        <div className="flex items-center gap-2">
          {["projects", "knowledge_base"].map((b) => (
            <button
              key={b}
              onClick={() => setActiveBase(b)}
              className={`px-4 py-2 rounded-md ${
                activeBase === b
                  ? "bg-primary text-white"
                  : "bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-300"
              }`}
            >
              {b === "projects" ? "Projects" : "Knowledge Base"}
            </button>
          ))}

          <button
            onClick={() => loadExplorer(activeBase)}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCcw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Upload (only for knowledge_base) */}
      {activeBase === "knowledge_base" && (
        <>
          <div className="flex gap-4">
            <label className="flex-1 flex items-center justify-center gap-2 bg-primary text-white py-3 rounded-xl shadow hover:bg-secondary transition cursor-pointer">
              <Upload className="w-5 h-5" />
              Upload File
              <input type="file" className="hidden" onChange={onUploadFile} />
            </label>

            <label className="flex-1 flex items-center justify-center gap-2 bg-primary text-white py-3 rounded-xl shadow hover:bg-secondary transition cursor-pointer">
              <Folder className="w-5 h-5" />
              Upload Folder
              <input
                type="file"
                multiple
                webkitdirectory=""
                mozdirectory=""
                directory=""
                className="hidden"

                onChange={onUploadFolder}
              />
            </label>
          </div>

          {/* Case Study Section */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-800 dark:to-gray-700 rounded-xl border-2 border-blue-200 dark:border-blue-800 p-6 shadow-md">
            <h2 className="text-xl font-bold text-blue-900 dark:text-blue-100 mb-3 flex items-center gap-2">
              <FileIcon className="w-5 h-5" />
              Case Study
            </h2>
            <p className="text-sm text-blue-700 dark:text-blue-300 mb-4">
              Upload case study PPT files here. They will be automatically processed and used to match with your projects.
            </p>
            <label className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg shadow hover:shadow-lg transition cursor-pointer">
              <Upload className="w-5 h-5" />
              Upload Case Study File
              <input
                type="file"
                className="hidden"
                accept=".ppt,.pptx"
                onChange={async (e) => {
                  const f = e.target.files[0];
                  if (f) {
                    // Upload to case_study folder
                    await uploadFile(f, "case_study", activeBase);
                    await loadExplorer(activeBase);
                  }
                }}
              />
            </label>
            <p className="text-xs text-blue-600 dark:text-blue-400 mt-2">
              Accepted formats: .ppt, .pptx
            </p>
          </div>
        </>
      )}

      {/* File Tree */}
      <div className="bg-white dark:bg-dark-surface rounded-xl shadow-md border border-gray-200 dark:border-dark-muted p-6">
        <h2 className="text-lg font-semibold mb-4 text-gray-700 dark:text-gray-100">
          {activeBase === "projects"
            ? "Projects Files & Folders"
            : "Knowledge Base Files & Folders"}
        </h2>

        {loading ? (
          <p>Loading...</p>
        ) : !tree || tree.length === 0 ? (
          <p className="text-gray-500 dark:text-gray-400">
            No blobs yet. Upload something!
          </p>
        ) : (
          <ul className="space-y-2">
            {tree.map((node) => (
              <FolderNode
                key={node.path}
                node={node}
                base={activeBase}
                deleteFile={deleteFile}
                deleteFolder={deleteFolder}
                previewFile={previewFile}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

