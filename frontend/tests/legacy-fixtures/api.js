import { initialMockData } from './mockData.js';

class ApiService {
  constructor() {
    this.documents = [...initialMockData.documents];
    this.dataSources = [...initialMockData.dataSources];
    this.ingestionJobs = [...initialMockData.ingestionJobs];
    this.auditEvents = [...initialMockData.auditEvents];
    this.aiEnrichment = { ...initialMockData.aiEnrichment };

    const savedStr = typeof localStorage !== 'undefined' ? localStorage.getItem('nexus_saved_docs') : null;
    this.savedItemIds = new Set(JSON.parse(savedStr || '[]'));

    const authStored = typeof localStorage !== 'undefined' ? localStorage.getItem('nexus_token') : null;
    this.authenticated = Boolean(authStored);
  }

  isAuthenticated() {
    return this.authenticated;
  }

  login({ email }) {
    this.authenticated = true;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('nexus_token', `mock-token-${Date.now()}`);
      localStorage.setItem('nexus_role', 'admin');
    }
    this.logAudit({
      action: 'Admin Sign In',
      target: `User: ${email}`,
      details: 'Session authenticated.',
    });
    return true;
  }

  logout() {
    this.authenticated = false;
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('nexus_token');
      localStorage.removeItem('nexus_role');
      localStorage.removeItem('nexus_user');
    }
    return true;
  }

  async search({
    query = '',
    mode = 'natural',
    modalities = [],
    sources = [],
    minConfidence = 0,
    sortBy = 'relevance',
  }) {
    await new Promise((r) => setTimeout(r, 40));
    const normalizedQuery = query.trim().toLowerCase();
    const queryTokens = normalizedQuery.split(/\s+/).filter(Boolean);

    let candidates = [...this.documents];

    if (normalizedQuery.length > 0) {
      candidates = candidates
        .map((doc) => {
          let score = 0;
          const haystack = [
            doc.filename,
            doc.aiDescription,
            doc.canonicalCaption,
            doc.ocrText || '',
            doc.transcript || '',
            doc.tags.join(' '),
            doc.source,
          ]
            .join(' ')
            .toLowerCase();

          if (haystack.includes(normalizedQuery)) score += 0.5;

          let tokenMatches = 0;
          for (const token of queryTokens) {
            if (haystack.includes(token)) {
              tokenMatches++;
              if (doc.tags.some((t) => t.toLowerCase().includes(token))) score += 0.15;
              if (doc.filename.toLowerCase().includes(token)) score += 0.2;
            }
          }

          const tokenRatio = queryTokens.length > 0 ? tokenMatches / queryTokens.length : 0;
          score += tokenRatio * 0.4;
          const finalScore =
            tokenMatches > 0
              ? Math.min(
                  0.99,
                  Math.max(0.65, Number((score * 0.6 + (doc.relevanceScore || 0.85) * 0.4).toFixed(3)))
                )
              : 0;

          return { ...doc, searchScore: finalScore };
        })
        .filter((doc) => doc.searchScore > 0);
    } else {
      candidates = candidates.map((doc) => ({ ...doc, searchScore: doc.relevanceScore }));
    }

    if (modalities.length > 0) {
      candidates = candidates.filter((d) => modalities.includes(d.modality));
    }

    if (sources.length > 0) {
      candidates = candidates.filter((d) => sources.includes(d.source));
    }

    if (minConfidence > 0) {
      candidates = candidates.filter((d) => d.confidence * 100 >= minConfidence);
    }

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
      results: candidates,
    };
  }

  getDocument(id) {
    return this.documents.find((d) => d.id === id) || null;
  }

  toggleSaveDocument(id) {
    if (this.savedItemIds.has(id)) {
      this.savedItemIds.delete(id);
    } else {
      this.savedItemIds.add(id);
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('nexus_saved_docs', JSON.stringify([...this.savedItemIds]));
    }
    return this.savedItemIds.has(id);
  }

  isDocumentSaved(id) {
    return this.savedItemIds.has(id);
  }

  getDataSources() {
    return [...this.dataSources];
  }

  addDataSource({ name, bucketName, region, iamRoleArn, authType, syncInterval, prefix }) {
    const newSource = {
      id: `s3-src-${String(this.dataSources.length + 1).padStart(3, '0')}`,
      name: name || `S3 / ${bucketName}`,
      type: 'Amazon S3',
      bucketName: bucketName || 'nexus-data-bucket',
      endpoint: `s3://${bucketName || 'nexus-data-bucket'}/${prefix ? prefix.replace(/^\/+|\/+$/g, '') + '/' : ''}`,
      status: 'Connected',
      syncStatus: syncInterval || 'Continuous EventStream',
      lastSync: new Date().toISOString(),
      discoveredFiles: 0,
      totalBytes: '0 B',
      region: region || 'ap-east-1',
      authType: authType || 'IAM Role Delegation',
      iamRoleArn: iamRoleArn || 'arn:aws:iam::123456789012:role/NexusS3IngestRole',
      syncInterval: syncInterval || 'Continuous EventStream',
      fileTypes: ['JPG', 'MP4', 'PDF', 'CSV'],
    };
    this.dataSources.unshift(newSource);
    this.logAudit({
      action: 'S3 Bucket Connected',
      target: `Bucket: ${newSource.endpoint}`,
      details: `Configured S3 connector in ${newSource.region} with ${newSource.authType} (${newSource.syncInterval})`,
    });
    return newSource;
  }

  getIngestionJobs() {
    return [...this.ingestionJobs];
  }

  getAuditEvents() {
    return [...this.auditEvents];
  }

  logAudit({ action, target, details, status = 'Success' }) {
    const event = {
      id: `evt-${Date.now()}`,
      timestamp: new Date().toISOString(),
      user: initialMockData.currentUser.email,
      role: initialMockData.currentUser.role,
      department: initialMockData.currentUser.division,
      action,
      target,
      status,
      complianceCode: `AUD-${Math.floor(1000 + Math.random() * 9000)}`,
      details,
    };
    this.auditEvents.unshift(event);
    return event;
  }
}

export const api = new ApiService();
