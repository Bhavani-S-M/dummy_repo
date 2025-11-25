// src/api/etlApi.js
import api from "./axiosClient";

const etlApi = {
  /**
   * Trigger manual ETL scan
   */
  triggerScan: () => api.post("/etl/scan"),

  /**
   * Get ETL scan status (whether scan is running)
   */
  getScanStatus: () => api.get("/etl/scan/status"),

  /**
   * Get pending KB updates requiring approval
   * @param {string} status - Filter by status: pending, approved, rejected
   * @param {number} limit - Number of results to return
   * @param {number} offset - Offset for pagination
   */
  getPendingUpdates: (status = "pending", limit = 50, offset = 0) =>
    api.get("/etl/pending-updates", {
      params: { status, limit, offset },
    }),

  /**
   * Approve a pending KB update
   * @param {string} pendingUpdateId - UUID of the pending update
   * @param {string} adminComment - Optional admin comment
   */
  approvePendingUpdate: (pendingUpdateId, adminComment = null) =>
    api.post(`/etl/approve/${pendingUpdateId}`, { admin_comment: adminComment }),

  /**
   * Reject a pending KB update
   * @param {string} pendingUpdateId - UUID of the pending update
   * @param {string} adminComment - Optional admin comment
   */
  rejectPendingUpdate: (pendingUpdateId, adminComment = null) =>
    api.post(`/etl/reject/${pendingUpdateId}`, { admin_comment: adminComment }),

  /**
   * Get processing jobs
   * @param {string} status - Filter by status: pending, processing, completed, failed
   * @param {number} limit - Number of results to return
   * @param {number} offset - Offset for pagination
   */
  getProcessingJobs: (status = null, limit = 50, offset = 0) => {
    const params = { limit, offset };
    if (status) params.status = status;
    return api.get("/etl/processing-jobs", { params });
  },

  /**
   * Get KB documents
   * @param {boolean} isVectorized - Filter by vectorization status
   * @param {number} limit - Number of results to return
   * @param {number} offset - Offset for pagination
   */
  getKBDocuments: (isVectorized = null, limit = 50, offset = 0) => {
    const params = { limit, offset };
    if (isVectorized !== null) params.is_vectorized = isVectorized;
    return api.get("/etl/kb-documents", { params });
  },

  /**
   * Get ETL pipeline statistics
   */
  getStats: () => api.get("/etl/stats"),

  /**
   * Reset failed documents to allow reprocessing
   */
  resetFailedDocuments: () => api.post("/etl/reset-failed-documents"),
};

export default etlApi;
