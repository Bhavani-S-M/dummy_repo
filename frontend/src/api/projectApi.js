// src/api/projectApi.js
import api from "./axiosClient";

const appendIfPresent = (formData, key, value) => {
  if (value === undefined || value === null) return;
  const v = typeof value === "string" ? value.trim() : value;
  if (v !== "" && v !== null && v !== undefined) {
    formData.append(key, v);
  }
};

const projectApi = {
  getProjects: ({ signal } = {}) => api.get("/projects", { signal }),

  getProject: (id, { signal } = {}) => api.get(`/projects/${id}`, { signal }),

  createProject: (data) => {
    const formData = new FormData();
    appendIfPresent(formData, "name", data.name);
    appendIfPresent(formData, "domain", data.domain);
    appendIfPresent(formData, "complexity", data.complexity);
    appendIfPresent(formData, "tech_stack", data.tech_stack);
    appendIfPresent(formData, "use_cases", data.use_cases);
    appendIfPresent(formData, "duration", data.duration);

    if (Array.isArray(data.compliance)) {
      data.compliance.forEach((c) => formData.append("compliance", c));
    } else {
      appendIfPresent(formData, "compliance", data.compliance);
    }

    appendIfPresent(formData, "company_id", data.company_id);

    if (Array.isArray(data.files) && data.files.length > 0) {
      data.files.forEach((item) => {
        const fileObj = item?.file || item;
        if (fileObj instanceof File || fileObj instanceof Blob) {
          formData.append("files", fileObj);
        }
        if (item?.type) {
          formData.append("file_types", String(item.type));
        }
      });
    }

    return api.post("/projects", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  updateProject: (id, updateData) => api.put(`/projects/${id}`, updateData),

  deleteProject: (id) => api.delete(`/projects/${id}`),

  deleteAllProjects: () => api.delete("/projects"),

  generateScope: (id, { signal } = {}) =>
    api.get(`/projects/${id}/generate_scope`, { signal }),

  finalizeScope: (id, scopeData, { signal } = {}) =>
    api.post(`/projects/${id}/finalize_scope`, scopeData, {
      headers: { "Content-Type": "application/json" },
      signal,
    }),

  regenerateScope: (id, data, { signal } = {}) =>
    api.post(`/projects/${id}/regenerate_scope`, data, {
      headers: { "Content-Type": "application/json" },
      signal,
    }),

  generateQuestions: (id) =>
    api.post(`/projects/${id}/generate_questions`),

  updateQuestions: (id, answers) =>
    api.post(`/projects/${id}/update_questions`, answers, {
      headers: { "Content-Type": "application/json" },
    }),

  getQuestions: (id) => api.get(`/projects/${id}/questions`),

  getFinalizedScope: (id, { signal } = {}) =>
    api.get(`/projects/${id}/finalized_scope`, { signal }),

  getRelatedCaseStudy: (id, { signal } = {}) =>
    api.get(`/projects/${id}/related_case_study`, { signal }),

  getDownloadUrl: (filePath, base = "projects") =>
    `${api.defaults.baseURL}/blobs/download/${filePath}?base=${base}`,

  getPreviewUrl: (filePath, base = "projects") =>
    `${api.defaults.baseURL}/blobs/preview/${filePath}?base=${base}`,
};

export default projectApi;
