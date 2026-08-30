/**
 * Aegis Platform Enterprise Data Platform - Mock Data Architecture
 * S3-focused dataset
 */

export const initialMockData = {
  platformOverview: {
    totalIndexedFiles: 14892410,
    totalStorageFormatted: "1.84 PB",
    filesProcessed: 14652190,
    enrichmentRate: 98.4,
    activeIngestionJobs: 3,
    aiProcessingThroughput: "420 docs/sec",
    searchLatencyAvgMs: 38,
    failedItemsCount: 124,
    storageSystemsConnected: 4,
    modalityDistribution: [
      { type: "image", label: "Images", count: 7840120, bytes: "842 TB", percentage: 52.6 },
      { type: "video", label: "Videos", count: 1890300, bytes: "620 TB", percentage: 12.7 },
      { type: "document", label: "Documents (PDF/DOCX)", count: 2840000, bytes: "185 TB", percentage: 19.1 },
      { type: "audio", label: "Audio & Transcripts", count: 1320000, bytes: "148 TB", percentage: 8.9 },
      { type: "tabular", label: "Tabular & Sensor Logs", count: 1001990, bytes: "45 TB", percentage: 6.7 }
    ]
  },

  dataSources: [
    {
      id: "s3-src-001",
      name: "Production S3 Display Inspection",
      type: "Amazon S3",
      bucketName: "nexus-inspection-raw-apne2",
      endpoint: "s3://nexus-inspection-raw-apne2/line04/2026/",
      status: "Connected",
      syncStatus: "Continuous EventStream",
      lastSync: "2026-08-20T21:45:00Z",
      discoveredFiles: 6820100,
      totalBytes: "712.4 TB",
      region: "ap-northeast-2 (Seoul)",
      authType: "IAM Role Delegation",
      syncInterval: "S3 EventBridge Trigger",
      fileTypes: ["JPG", "PNG", "RAW", "MP4", "CSV"]
    },
    {
      id: "s3-src-002",
      name: "S3 Defect Telemetry & Quality Vault",
      type: "Amazon S3",
      bucketName: "nexus-defect-telemetry-vault",
      endpoint: "s3://nexus-defect-telemetry-vault/quality-records/2026/",
      status: "Connected",
      syncStatus: "Hourly Ingest",
      lastSync: "2026-08-20T21:15:00Z",
      discoveredFiles: 3920400,
      totalBytes: "510.2 TB",
      region: "ap-northeast-2 (Seoul)",
      authType: "IAM Role Delegation",
      syncInterval: "Every 1 hour",
      fileTypes: ["PDF", "DOCX", "CSV", "JSON"]
    },
    {
      id: "s3-src-003",
      name: "S3 R&D Multimodal Audio & Media Archive",
      type: "Amazon S3",
      bucketName: "nexus-rd-multimodal-archive",
      endpoint: "s3://nexus-rd-multimodal-archive/sensors_and_audio/",
      status: "Connected",
      syncStatus: "Continuous Stream",
      lastSync: "2026-08-20T21:50:00Z",
      discoveredFiles: 2420800,
      totalBytes: "348.6 TB",
      region: "ap-northeast-2 (Seoul)",
      authType: "IAM Role Delegation",
      syncInterval: "Continuous SQS Queue",
      fileTypes: ["WAV", "FLAC", "MP4", "TXT"]
    },
    {
      id: "s3-src-004",
      name: "S3 Cleanroom Optical Sensor Stream",
      type: "Amazon S3",
      bucketName: "nexus-cleanroom-sensor-stream",
      endpoint: "s3://nexus-cleanroom-sensor-stream/live-captures/",
      status: "Connected",
      syncStatus: "Real-time Stream",
      lastSync: "2026-08-20T21:54:00Z",
      discoveredFiles: 1731110,
      totalBytes: "268.8 TB",
      region: "ap-northeast-2 (Seoul)",
      authType: "IAM Role Delegation",
      syncInterval: "Continuous Ingest",
      fileTypes: ["JPG", "MP4", "TIF"]
    }
  ],

  ingestionJobs: [
    {
      id: "job-ing-01",
      name: "S3 / Production Inspection Stream",
      sourceName: "Production S3 Display Inspection",
      bucket: "nexus-inspection-raw-apne2",
      status: "Processing",
      stage: "Validating",
      discoveredCount: 2483920,
      validatedCount: 2461104,
      duplicateCount: 22816,
      failedCount: 1124,
      dataVolume: "48.7 TB",
      currentThroughput: "18.4 GB/s",
      stages: [
        { name: "S3 Object Discovery", status: "completed", progress: 100 },
        { name: "Stream Validation", status: "active", progress: 99.1 },
        { name: "Checksum Deduplication", status: "active", progress: 98.4 },
        { name: "UUID v7 Registration", status: "pending", progress: 85.0 }
      ]
    },
    {
      id: "job-ing-02",
      name: "S3 / Cleanroom High-Speed Optical Feed",
      sourceName: "S3 Cleanroom Optical Sensor Stream",
      bucket: "nexus-cleanroom-sensor-stream",
      status: "Processing",
      stage: "Streaming",
      discoveredCount: 1240000,
      validatedCount: 980200,
      duplicateCount: 8400,
      failedCount: 310,
      dataVolume: "32.1 TB",
      currentThroughput: "12.8 GB/s",
      stages: [
        { name: "S3 Object Discovery", status: "completed", progress: 100 },
        { name: "Stream Validation", status: "active", progress: 79.0 },
        { name: "Checksum Deduplication", status: "pending", progress: 68.0 },
        { name: "UUID v7 Registration", status: "pending", progress: 50.0 }
      ]
    },
    {
      id: "job-ing-03",
      name: "S3 / Quality Vault Monthly Batch",
      sourceName: "S3 Defect Telemetry & Quality Vault",
      bucket: "nexus-defect-telemetry-vault",
      status: "Completed",
      stage: "Completed",
      discoveredCount: 450200,
      validatedCount: 449850,
      duplicateCount: 350,
      failedCount: 0,
      dataVolume: "14.2 TB",
      currentThroughput: "0.0 GB/s",
      stages: [
        { name: "S3 Object Discovery", status: "completed", progress: 100 },
        { name: "Stream Validation", status: "completed", progress: 100 },
        { name: "Checksum Deduplication", status: "completed", progress: 100 },
        { name: "UUID v7 Registration", status: "completed", progress: 100 }
      ]
    }
  ],

  aiEnrichment: {
    activePipelines: [
      { id: "pipe-01", name: "Vision-LLM 9.4B Multimodal Inspector", modality: "image", throughput: "210 img/sec", latencyAvg: "142 ms", queueSize: 1420, status: "Healthy" },
      { id: "pipe-02", name: "Whisper-Large-v3 Audio Transcription Engine", modality: "audio", throughput: "45 stream/sec", latencyAvg: "480 ms", queueSize: 280, status: "Healthy" },
      { id: "pipe-03", name: "OCR Layout Engine v4 & Document Parser", modality: "document", throughput: "120 doc/sec", latencyAvg: "88 ms", queueSize: 810, status: "Healthy" },
      { id: "pipe-04", name: "ViT-H/14 Multimodal Vector Embedding Model", modality: "all", throughput: "650 vec/sec", latencyAvg: "24 ms", queueSize: 3100, status: "Healthy" }
    ],
    // Correct sequential step progression:
    // Step 1: Completed, Step 2: Completed, Step 3: Active, Step 4: Pending
    stages: [
      { id: "stage-1", name: "S3 Validated Stream", count: 1840, status: "completed" },
      { id: "stage-2", name: "Content Extraction & OCR", count: 1240, status: "completed" },
      { id: "stage-3", name: "Vision-LLM & Acoustic Tagging", count: 810, status: "active" },
      { id: "stage-4", name: "1536-d Embedding & Indexing", count: 420, status: "pending" }
    ],
    confidenceDistribution: [
      { range: "95% - 100%", count: "10.8M docs", percentage: 73.7 },
      { range: "90% - 94%", count: "2.8M docs", percentage: 19.1 },
      { range: "80% - 89%", count: "840K docs", percentage: 5.7 },
      { range: "Below 80%", count: "212K docs", percentage: 1.5 }
    ]
  },

  documents: [
    {
      id: "0197f3c2-7a11-7c4a-b9e2-2a7f6d3e91c4",
      filename: "OLED_Line04_Inspection_0421.jpg",
      contentType: "image/jpeg",
      modality: "image",
      fileSize: "14.2 MB",
      fileSizeBytes: 14889728,
      source: "Production S3 Display Inspection",
      sourceUri: "s3://nexus-inspection-raw-apne2/line04/2026/04/OLED_Line04_Inspection_0421.jpg",
      checksum: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      createdAt: "2026-04-18T09:22:14Z",
      processedAt: "2026-04-18T09:23:02Z",
      relevanceScore: 0.984,
      aiDescription: "Close-up optical inspection image showing a micro-fissure crack along the upper-right bezel perimeter of an active OLED mobile display panel module.",
      canonicalCaption: "Cracked OLED display perimeter microfracture on Line 04 inspection jig.",
      tags: ["OLED", "display", "crack", "inspection", "manufacturing", "bezel", "microfracture"],
      detectedObjects: [
        { label: "Mobile Display Panel", confidence: 0.994, box: [12, 15, 88, 85] },
        { label: "Glass Surface Fissure", confidence: 0.968, box: [68, 18, 82, 34] }
      ],
      ocrText: "SEC-DISP-MOD-0421-2026 REV 2.4 / LOT 8849-B / INSPECT STATION 04-B",
      transcript: null,
      confidence: 0.968,
      governance: "Confidential",
      embeddingVectorDim: 1536
    },
    {
      id: "0197f3c2-8b22-7d5b-a8f3-3b8e7e4f02d5",
      filename: "Display_Crack_Inspection_0178.jpg",
      contentType: "image/jpeg",
      modality: "image",
      fileSize: "12.8 MB",
      fileSizeBytes: 13421772,
      source: "Production S3 Display Inspection",
      sourceUri: "s3://nexus-inspection-raw-apne2/line04/2026/04/Display_Crack_Inspection_0178.jpg",
      checksum: "a1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
      createdAt: "2026-04-17T14:10:05Z",
      processedAt: "2026-04-17T14:11:12Z",
      relevanceScore: 0.962,
      aiDescription: "Automated optical inspection image capturing transverse glass fracture propagation originating from corner pressure point during panel lamination.",
      canonicalCaption: "Lamination fracture on OLED display corner during pressure test sequence.",
      tags: ["display", "crack", "OLED", "lamination", "fracture", "quality", "panel"],
      detectedObjects: [
        { label: "OLED Screen Module", confidence: 0.988, box: [10, 10, 90, 90] },
        { label: "Stress Fracture Point", confidence: 0.954, box: [14, 12, 32, 28] }
      ],
      ocrText: "LAM-FAIL-0178 // PRESSURE 4.2 BAR // DELTA 0.8MM",
      transcript: null,
      confidence: 0.954,
      governance: "Confidential",
      embeddingVectorDim: 1536
    },
    {
      id: "0197f3c2-9c33-7e6c-b904-4c9f8f5a13e6",
      filename: "Panel_Assembly_Line02_0912.mp4",
      contentType: "video/mp4",
      modality: "video",
      fileSize: "148.5 MB",
      fileSizeBytes: 155713536,
      source: "S3 Cleanroom Optical Sensor Stream",
      sourceUri: "s3://nexus-cleanroom-sensor-stream/live-captures/Panel_Assembly_Line02_0912.mp4",
      checksum: "7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d",
      createdAt: "2026-04-16T11:05:42Z",
      processedAt: "2026-04-16T11:08:19Z",
      relevanceScore: 0.948,
      aiDescription: "Cleanroom recording showing automated robotic arms and technicians assembling flexible OLED display panels onto mid-frame housing.",
      canonicalCaption: "Robotic high-precision pick and place of OLED panel module onto chassis Line 02.",
      tags: ["assembly", "OLED", "workers", "manufacturing", "panel", "robotic"],
      detectedObjects: [
        { label: "Cleanroom Technician", confidence: 0.978, box: [20, 30, 45, 85] }
      ],
      ocrText: "STATION 02-D // CYCLE TIME 18.2s // TACT OK",
      transcript: "Operator: Beginning lot 44 cycle. Pick position verified at coordinate delta zero.",
      confidence: 0.962,
      governance: "Restricted",
      embeddingVectorDim: 1536
    },
    {
      id: "0197f3c2-a144-7f7d-c015-5d0a906b24f7",
      filename: "Quality_Failure_Report_Q2.pdf",
      contentType: "application/pdf",
      modality: "document",
      fileSize: "8.4 MB",
      fileSizeBytes: 8808038,
      source: "S3 Defect Telemetry & Quality Vault",
      sourceUri: "s3://nexus-defect-telemetry-vault/quality-records/2026/Quality_Failure_Report_Q2.pdf",
      checksum: "4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c",
      createdAt: "2026-04-15T08:00:00Z",
      processedAt: "2026-04-15T08:01:45Z",
      relevanceScore: 0.935,
      aiDescription: "Engineering quality assurance failure analysis document detailing display panel edge crack anomalies, mechanical stress root cause, and corrective action protocols.",
      canonicalCaption: "Q2 Failure Analysis for OLED Substrate Micro-cracks.",
      tags: ["report", "quality", "failure", "OLED", "crack", "display", "analysis", "pdf"],
      detectedObjects: [],
      ocrText: "CONFIDENTIAL ENGINEERING REPORT: Q2 ROOT CAUSE ANALYSIS ON OLED EDGE MICROFRACTURES.",
      transcript: null,
      confidence: 0.974,
      governance: "Confidential",
      embeddingVectorDim: 1536
    },
    {
      id: "0197f3c2-c366-719f-e237-7f2c128d46b9",
      filename: "Ultrasonic_Motor_Acoustic_0891.wav",
      contentType: "audio/wav",
      modality: "audio",
      fileSize: "28.4 MB",
      fileSizeBytes: 29779558,
      source: "S3 R&D Multimodal Audio & Media Archive",
      sourceUri: "s3://nexus-rd-multimodal-archive/sensors_and_audio/Ultrasonic_Motor_Acoustic_0891.wav",
      checksum: "d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2",
      createdAt: "2026-04-14T10:45:00Z",
      processedAt: "2026-04-14T10:45:48Z",
      relevanceScore: 0.895,
      aiDescription: "Acoustic emission recording of assembly line positioning motor during high-speed vacuum pickup cycles showing harmonic vibration anomaly.",
      canonicalCaption: "Acoustic vibration spectrum of Line 04 positioning motor.",
      tags: ["audio", "acoustic", "motor", "vibration", "ultrasonic", "sensor", "anomaly"],
      detectedObjects: [],
      ocrText: null,
      transcript: "Spectral Analysis: Harmonic spike detected at 38.4 kHz indicative of bearing race degradation.",
      confidence: 0.942,
      governance: "Internal",
      embeddingVectorDim: 1536
    },
    {
      id: "0197f3c2-f299-74cf-1560-a2fb451079d2",
      filename: "Panel_Defect_Records_2026.csv",
      contentType: "text/csv",
      modality: "tabular",
      fileSize: "18.6 MB",
      fileSizeBytes: 19503513,
      source: "S3 Defect Telemetry & Quality Vault",
      sourceUri: "s3://nexus-defect-telemetry-vault/quality-records/2026/Panel_Defect_Records_2026.csv",
      checksum: "5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f",
      createdAt: "2026-04-18T18:00:00Z",
      processedAt: "2026-04-18T18:02:10Z",
      relevanceScore: 0.854,
      aiDescription: "Structured CSV dataset logging 48,200 manufacturing defect events across OLED lines, detailing defect coordinates, severity, and optical sensor values.",
      canonicalCaption: "2026 OLED Line Defect Telemetry Records Matrix.",
      tags: ["csv", "defect", "records", "OLED", "panel", "tabular"],
      detectedObjects: [],
      ocrText: "timestamp,panel_id,line_id,defect_type,severity_score,pass_fail\n2026-04-18T08:12:01Z,SEC-OLED-88912,LINE04,CORNER_CRACK,0.89,FAIL",
      transcript: null,
      confidence: 0.992,
      governance: "Confidential",
      embeddingVectorDim: 1536
    }
  ],

  auditEvents: [
    {
      id: "evt-01",
      timestamp: "2026-08-20T21:42:15Z",
      user: "admin@platform.internal",
      role: "Platform Administrator",
      department: "Data Platform Division",
      action: "Multimodal Search Query",
      target: "Query: 'Cracked OLED display panels'",
      status: "Success",
      complianceCode: "AUD-SRCH-9921"
    },
    {
      id: "evt-02",
      timestamp: "2026-08-20T21:38:04Z",
      user: "admin@platform.internal",
      role: "Platform Administrator",
      department: "Data Platform Division",
      action: "S3 Object Inspection",
      target: "s3://nexus-inspection-raw-apne2/line04/2026/04/OLED_Line04_Inspection_0421.jpg",
      status: "Success",
      complianceCode: "AUD-INSP-4412"
    }
  ],

  currentUser: {
    name: "Alex Kim",
    email: "admin@platform.internal",
    role: "Platform Administrator",
    division: "Nexus Platform / Data Platform",
    workspace: "Production S3 Data Fabric",
    environment: "PRD-AP-EAST-1"
  }
};
