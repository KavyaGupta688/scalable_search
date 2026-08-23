/**
 * Samsung Prism Enterprise API & State Service
 * 
 * S3-focused data service with search, S3 bucket connectors, manual S3 object ingestion,
 * and session authentication management.
 */

import { mockData } from './mock-data.js';

class ApiService {
  constructor() {
    this.documents = [...mockData.documents];
    this.dataSources = [...mockData.dataSources];
    this.ingestionJobs = [...mockData.ingestionJobs];
    this.auditEvents = [...mockData.auditEvents];
    const savedStr = typeof localStorage !== 'undefined' ? localStorage.getItem('prism-saved-docs') : null;
    this.savedItemIds = new Set(JSON.parse(savedStr || '[]'));
    
    // Auth state: default to false or checked from localStorage
    const authStored = typeof localStorage !== 'undefined' ? localStorage.getItem('prism-auth') : null;
    this.authenticated = authStored === 'true';
  }

  // Authentication
  isAuthenticated() {
    return this.authenticated;
  }

  login({ email, password, mfaCode }) {
    this.authenticated = true;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('prism-auth', 'true');
    }
    this.logAudit({
      action: 'Admin Sign In',
      target: `User: ${email}`,
      details: 'MFA authentication verified.'
    });
    return true;
  }

  logout() {
    this.authenticated = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('prism-auth');
    }
    return true;
  }

  // Search Engine
  async search({
    query = '',
    mode = 'natural',
    modalities = [],
    sources = [],
    tags = [],
    governances = [],
    minConfidence = 0,
    referenceDocId = null,
    sortBy = 'relevance'
  }) {
    await new Promise(r => setTimeout(r, 40));

    const normalizedQuery = query.trim().toLowerCase();
    const queryTokens = normalizedQuery.split(/\s+/).filter(Boolean);

    let candidates = [...this.documents];

    if (mode === 'similar' && referenceDocId) {
      const refDoc = this.documents.find(d => d.id === referenceDocId);
      if (refDoc) {
        candidates = candidates.map(doc => {
          if (doc.id === refDoc.id) return { ...doc, searchScore: 1.0 };
          let score = 0.5;
          const sharedTags = doc.tags.filter(t => refDoc.tags.includes(t));
          score += (sharedTags.length / Math.max(1, refDoc.tags.length)) * 0.35;
          if (doc.modality === refDoc.modality) score += 0.1;
          if (doc.source === refDoc.source) score += 0.05;
          return { ...doc, searchScore: Math.min(0.99, Number(score.toFixed(3))) };
        });
      }
    } else if (normalizedQuery.length > 0) {
      candidates = candidates.map(doc => {
        let score = 0;
        const haystack = [
          doc.filename,
          doc.aiDescription,
          doc.canonicalCaption,
          doc.ocrText || '',
          doc.transcript || '',
          doc.tags.join(' '),
          doc.entities.map(e => e.name).join(' '),
          doc.source
        ].join(' ').toLowerCase();

        if (haystack.includes(normalizedQuery)) {
          score += 0.5;
        }

        let tokenMatches = 0;
        for (const token of queryTokens) {
          if (haystack.includes(token)) {
            tokenMatches++;
            if (doc.tags.some(t => t.toLowerCase().includes(token))) score += 0.15;
            if (doc.filename.toLowerCase().includes(token)) score += 0.2;
            if (doc.ocrText && doc.ocrText.toLowerCase().includes(token)) score += 0.15;
            if (doc.transcript && doc.transcript.toLowerCase().includes(token)) score += 0.15;
          }
        }

        const tokenRatio = queryTokens.length > 0 ? (tokenMatches / queryTokens.length) : 0;
        score += tokenRatio * 0.4;

        const baseScore = doc.relevanceScore || 0.85;
        const finalScore = tokenMatches > 0 ? Math.min(0.99, Math.max(0.65, Number((score * 0.6 + baseScore * 0.4).toFixed(3)))) : 0;

        return { ...doc, searchScore: finalScore };
      }).filter(doc => doc.searchScore > 0);
    } else {
      candidates = candidates.map(doc => ({ ...doc, searchScore: doc.relevanceScore }));
    }

    // Apply Facet Filters
    if (modalities.length > 0) {
      candidates = candidates.filter(d => modalities.includes(d.modality));
    }

    if (sources.length > 0) {
      candidates = candidates.filter(d => sources.includes(d.source));
    }

    if (tags.length > 0) {
      candidates = candidates.filter(d => tags.some(t => d.tags.map(x => x.toLowerCase()).includes(t.toLowerCase())));
    }

    if (governances.length > 0) {
      candidates = candidates.filter(d => governances.includes(d.governance));
    }

    if (minConfidence > 0) {
      candidates = candidates.filter(d => (d.confidence * 100) >= minConfidence);
    }

    // Sort
    if (sortBy === 'relevance') {
      candidates.sort((a, b) => (b.searchScore || 0) - (a.searchScore || 0));
    } else if (sortBy === 'date-desc') {
      candidates.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    } else if (sortBy === 'size-desc') {
      candidates.sort((a, b) => b.fileSizeBytes - a.fileSizeBytes);
    }

    return {
      query,
      mode,
      total: candidates.length,
      results: candidates
    };
  }

  // Get single document by ID
  getDocument(id) {
    return this.documents.find(d => d.id === id) || null;
  }

  // Saved items management
  toggleSaveDocument(id) {
    if (this.savedItemIds.has(id)) {
      this.savedItemIds.delete(id);
    } else {
      this.savedItemIds.add(id);
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('prism-saved-docs', JSON.stringify([...this.savedItemIds]));
    }
    return this.savedItemIds.has(id);
  }

  isDocumentSaved(id) {
    return this.savedItemIds.has(id);
  }

  // S3 Buckets / Data Sources
  getDataSources() {
    return [...this.dataSources];
  }

  addDataSource(source) {
    const newSource = {
      id: `s3-src-${String(this.dataSources.length + 1).padStart(3, '0')}`,
      name: source.name,
      type: "Amazon S3",
      bucketName: source.bucketName || source.name.toLowerCase().replace(/[^a-z0-9-]/g, '-'),
      endpoint: `s3://${source.bucketName || 'samsung-data-bucket'}/`,
      status: "Connected",
      syncStatus: "Connected",
      lastSync: new Date().toISOString(),
      discoveredFiles: 0,
      totalBytes: "0 B",
      ingestionState: "Active",
      enrichmentState: "Synchronized",
      region: source.region || "ap-northeast-2 (Seoul)",
      authType: "IAM Role Delegation",
      syncInterval: "Continuous SQS Queue",
      fileTypes: ["JPG", "MP4", "PDF", "CSV"]
    };
    this.dataSources.unshift(newSource);
    this.logAudit({
      action: 'S3 Bucket Connected',
      target: `Bucket: ${newSource.endpoint}`,
      details: `Configured S3 bucket connector in ${newSource.region}`
    });
    return newSource;
  }

  // Ingestion Jobs
  getIngestionJobs() {
    return [...this.ingestionJobs];
  }

  // Audit Events
  getAuditEvents() {
    return [...this.auditEvents];
  }

  logAudit({ action, target, details, status = 'Success' }) {
    const event = {
      id: `evt-${Date.now()}`,
      timestamp: new Date().toISOString(),
      user: mockData.currentUser.email,
      role: mockData.currentUser.role,
      department: mockData.currentUser.division,
      action,
      target,
      status,
      complianceCode: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      details
    };
    this.auditEvents.unshift(event);
    return event;
  }

  // S3 Manual Upload Simulation
  async processManualUpload(file) {
    await new Promise(r => setTimeout(r, 400));
    const uuidV7 = `0197f3c2-${Math.random().toString(16).slice(2, 6)}-7${Math.random().toString(16).slice(2, 5)}-b${Math.random().toString(16).slice(2, 5)}-${Math.random().toString(16).slice(2, 14)}`;
    
    const ext = file.name.split('.').pop().toLowerCase();
    let modality = 'document';
    if (['jpg', 'jpeg', 'png', 'tif', 'webp'].includes(ext)) modality = 'image';
    if (['mp4', 'avi', 'mov', 'webm'].includes(ext)) modality = 'video';
    if (['wav', 'flac', 'mp3', 'aac'].includes(ext)) modality = 'audio';
    if (['csv', 'xlsx', 'parquet'].includes(ext)) modality = 'tabular';

    const newDoc = {
      id: uuidV7,
      filename: file.name,
      contentType: file.type || `application/${ext}`,
      modality,
      fileSize: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
      fileSizeBytes: file.size,
      source: "Production S3 Display Inspection",
      sourceUri: `s3://samsung-inspection-raw-apne2/uploads/${file.name}`,
      checksum: "f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8",
      createdAt: new Date().toISOString(),
      processedAt: new Date().toISOString(),
      relevanceScore: 0.95,
      aiDescription: `Automated analysis of S3 ${modality} object '${file.name}'. Metadata extracted and 1536-d vector generated.`,
      canonicalCaption: `Ingested S3 object: ${file.name}`,
      tags: [modality, "S3", "inspection", "manufacturing"],
      detectedObjects: [],
      entities: [],
      ocrText: null,
      transcript: null,
      qualityScore: "Good",
      confidence: 0.975,
      governance: "Internal",
      piiStatus: "Not Detected",
      safetyStatus: "Passed",
      syntheticAiStatus: "Not Detected",
      embeddingVectorDim: 1536,
      similarDocIds: [],
      previewType: modality
    };

    this.documents.unshift(newDoc);
    this.logAudit({
      action: 'S3 Object Ingested',
      target: `s3://samsung-inspection-raw-apne2/uploads/${file.name}`,
      details: `Validated SHA-256 and queued for AI indexing.`
    });

    return newDoc;
  }
}

export const api = new ApiService();
