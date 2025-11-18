import { createContext, useContext, useState, useCallback } from "react";
import etlApi from "../api/etlApi";

const ETLContext = createContext();

export const ETLProvider = ({ children }) => {
  const [pendingUpdates, setPendingUpdates] = useState([]);
  const [processingJobs, setProcessingJobs] = useState([]);
  const [kbDocuments, setKBDocuments] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Trigger manual ETL scan
  const triggerScan = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.triggerScan();
      await loadStats(); // Refresh stats after scan
      return data;
    } catch (err) {
      console.error("ETL scan failed:", err);
      setError(err.response?.data?.detail || "ETL scan failed");
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Load pending updates
  const loadPendingUpdates = useCallback(async (status = "pending", limit = 50, offset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.getPendingUpdates(status, limit, offset);
      setPendingUpdates(data.pending_updates || []);
      return data;
    } catch (err) {
      console.error("Failed to load pending updates:", err);
      setError(err.response?.data?.detail || "Failed to load pending updates");
      return { pending_updates: [], count: 0 };
    } finally {
      setLoading(false);
    }
  }, []);

  // Approve pending update
  const approvePendingUpdate = useCallback(async (pendingUpdateId, adminComment = null) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.approvePendingUpdate(pendingUpdateId, adminComment);
      await loadPendingUpdates(); // Refresh pending updates
      await loadStats(); // Refresh stats
      return data;
    } catch (err) {
      console.error("Failed to approve update:", err);
      setError(err.response?.data?.detail || "Failed to approve update");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadPendingUpdates]);

  // Reject pending update
  const rejectPendingUpdate = useCallback(async (pendingUpdateId, adminComment = null) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.rejectPendingUpdate(pendingUpdateId, adminComment);
      await loadPendingUpdates(); // Refresh pending updates
      await loadStats(); // Refresh stats
      return data;
    } catch (err) {
      console.error("Failed to reject update:", err);
      setError(err.response?.data?.detail || "Failed to reject update");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadPendingUpdates]);

  // Load processing jobs
  const loadProcessingJobs = useCallback(async (status = null, limit = 50, offset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.getProcessingJobs(status, limit, offset);
      setProcessingJobs(data.jobs || []);
      return data;
    } catch (err) {
      console.error("Failed to load processing jobs:", err);
      setError(err.response?.data?.detail || "Failed to load processing jobs");
      return { jobs: [], count: 0 };
    } finally {
      setLoading(false);
    }
  }, []);

  // Load KB documents
  const loadKBDocuments = useCallback(async (isVectorized = null, limit = 50, offset = 0) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.getKBDocuments(isVectorized, limit, offset);
      setKBDocuments(data.documents || []);
      return data;
    } catch (err) {
      console.error("Failed to load KB documents:", err);
      setError(err.response?.data?.detail || "Failed to load KB documents");
      return { documents: [], count: 0 };
    } finally {
      setLoading(false);
    }
  }, []);

  // Load ETL stats
  const loadStats = useCallback(async () => {
    setError(null);
    try {
      const { data } = await etlApi.getStats();
      setStats(data.stats || null);
      return data.stats;
    } catch (err) {
      console.error("Failed to load ETL stats:", err);
      setError(err.response?.data?.detail || "Failed to load ETL stats");
      return null;
    }
  }, []);

  // Reset failed documents
  const resetFailedDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await etlApi.resetFailedDocuments();
      await loadStats(); // Refresh stats
      await loadProcessingJobs(); // Refresh jobs
      await loadKBDocuments(); // Refresh documents
      return data;
    } catch (err) {
      console.error("Failed to reset failed documents:", err);
      setError(err.response?.data?.detail || "Failed to reset failed documents");
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadStats, loadProcessingJobs, loadKBDocuments]);

  const value = {
    // State
    pendingUpdates,
    processingJobs,
    kbDocuments,
    stats,
    loading,
    error,

    // Actions
    triggerScan,
    loadPendingUpdates,
    approvePendingUpdate,
    rejectPendingUpdate,
    loadProcessingJobs,
    loadKBDocuments,
    loadStats,
    resetFailedDocuments,
  };

  return <ETLContext.Provider value={value}>{children}</ETLContext.Provider>;
};

export const useETL = () => {
  const context = useContext(ETLContext);
  if (!context) {
    throw new Error("useETL must be used within an ETLProvider");
  }
  return context;
};
