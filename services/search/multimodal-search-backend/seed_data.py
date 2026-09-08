import asyncio
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from qdrant_client.http import models as qmodels

from app.db.postgres import AsyncSessionLocal, init_db
from app.db.qdrant import get_qdrant_client, init_qdrant
from app.clients.embedding_client import get_embedding_client
from app.models.dataset import Dataset
from app.models.file_metadata import FileMetadata
from app.models.search_event import SearchEvent
from app.core.config import get_settings

settings = get_settings()

DATASETS_DATA = [
    {
        "id": "ds_geological_001",
        "name": "Geological Survey & Mineral Maps 2025",
        "description": "High-resolution satellite hyperspectral scans, mineral excavation maps, and core sample logs.",
        "category": "Nature",
        "thumbnail_url": "https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=600&auto=format&fit=crop&q=80",
        "view_count": 840,
        "download_count": 190,
        "search_hit_count": 310,
        "popularity_score": 1220.0
    },
    {
        "id": "ds_satellite_002",
        "name": "Satellite Earth Observation & Topography",
        "description": "Global multispectral orbital imagery, thermal surface maps, and elevation models.",
        "category": "Vehicles",
        "thumbnail_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop&q=80",
        "view_count": 720,
        "download_count": 165,
        "search_hit_count": 280,
        "popularity_score": 1050.0
    },
    {
        "id": "ds_safety_003",
        "name": "Industrial Safety & Equipment Video Audits",
        "description": "Factory inspection footage, PPE compliance audio transcripts, and machinery sensor logs.",
        "category": "Technology",
        "thumbnail_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=600&auto=format&fit=crop&q=80",
        "view_count": 530,
        "download_count": 120,
        "search_hit_count": 190,
        "popularity_score": 770.0
    },
    {
        "id": "ds_medical_004",
        "name": "Clinical Radiology & Pathology Imaging",
        "description": "High-fidelity CT scans, cellular microscopy, and diagnostic audio case reports.",
        "category": "Medical",
        "thumbnail_url": "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?w=600&auto=format&fit=crop&q=80",
        "view_count": 480,
        "download_count": 95,
        "search_hit_count": 150,
        "popularity_score": 670.0
    },
    {
        "id": "ds_autonomous_005",
        "name": "Autonomous Navigation & Telemetry Corpus",
        "description": "LiDAR point cloud extractions, dashcam video streams, and GPS telemetry timeseries.",
        "category": "Vehicles",
        "thumbnail_url": "https://images.unsplash.com/photo-1508974239320-0a029497e820?w=600&auto=format&fit=crop&q=80",
        "view_count": 410,
        "download_count": 88,
        "search_hit_count": 130,
        "popularity_score": 586.0
    },
    {
        "id": "ds_urban_006",
        "name": "Urban Architecture & BIM Structural Scans",
        "description": "3D photogrammetry, architectural CAD blueprints, and structural integrity reports.",
        "category": "Architecture",
        "thumbnail_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80",
        "view_count": 350,
        "download_count": 70,
        "search_hit_count": 110,
        "popularity_score": 490.0
    },
    {
        "id": "ds_wildlife_007",
        "name": "Global Wildlife & Biodiversity Acoustics",
        "description": "Bioacoustic audio recordings, species camera-trap images, and habitat telemetry.",
        "category": "Animals",
        "thumbnail_url": "https://images.unsplash.com/photo-1534188753412-3e26d0d618d6?w=600&auto=format&fit=crop&q=80",
        "view_count": 310,
        "download_count": 60,
        "search_hit_count": 90,
        "popularity_score": 430.0
    },
    {
        "id": "ds_energy_008",
        "name": "Renewable Wind & Solar Telemetry Logs",
        "description": "Clean energy sensor matrices, turbine vibration telemetry, and solar irradiance tables.",
        "category": "Technology",
        "thumbnail_url": "https://images.unsplash.com/photo-1466611653911-95081537e5b7?w=600&auto=format&fit=crop&q=80",
        "view_count": 290,
        "download_count": 52,
        "search_hit_count": 85,
        "popularity_score": 394.0
    }
]

FILES_DATA = [
    # 1. Geological & Mining (Nature)
    {
        "file_id": "file_geo_001",
        "dataset_id": "ds_geological_001",
        "dataset_name": "Geological Survey & Mineral Maps 2025",
        "file_name": "lithium_mineral_deposit_scan.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 4829100,
        "width": 3840,
        "height": 2160,
        "thumbnail_url": "https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1578328819058-b69f3a3b0f6b?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_geo_2025_01",
        "title": "Hyperspectral Mineral Map - Lithium & Rare Earth Basin",
        "description": "Hyperspectral satellite scan revealing high-grade spodumene and lithium deposits in arid basin terrain.",
        "tags": ["geology", "mineral", "lithium", "satellite", "infrared", "mining", "cartography"],
        "category": "Nature",
        "content_summary": "Topographic map identifying pegmatite ore bodies with estimated 1.8% lithium oxide concentration.",
        "ocr_text": "ZONE A-12 SPODUMENE ORE BODY LAT -23.54 LON 134.18 SPECTRAL BAND 7 INFRARED REFLECTANCE PEAK",
        "transcript": None,
        "caption": "A high-altitude false-color geological survey map showing vivid green and orange mineral deposit clusters.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_geo_002",
        "dataset_id": "ds_geological_001",
        "dataset_name": "Geological Survey & Mineral Maps 2025",
        "file_name": "coal_mining_strata_analysis.pdf",
        "file_type": "document",
        "mime_type": "application/pdf",
        "file_size": 8920400,
        "thumbnail_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_geo_2025_01",
        "title": "Subterranean Coal Mining Strata & Geotechnical Stability Report",
        "description": "Technical evaluation of coal seam integrity, seismic stress distribution, and methane drainage corridors.",
        "tags": ["coal", "mining", "geotechnical", "strata", "safety", "seismic", "report"],
        "category": "Nature",
        "content_summary": "Geotechnical cross-section analysis of bituminous coal bed at 420m depth showing roof bolt reinforcement factors.",
        "ocr_text": "TECHNICAL MEMORANDUM COAL MINING SEAM #4 STABILITY FACTOR 1.87 COMPRESSIVE STRENGTH 45 MPA METHANE DILUTION MONITORS ONLINE",
        "transcript": None,
        "caption": "Comprehensive engineering diagrams illustrating layered geological bedrock formations and mine shaft geometry.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_geo_003",
        "dataset_id": "ds_geological_001",
        "dataset_name": "Geological Survey & Mineral Maps 2025",
        "file_name": "core_drilling_sample_spectrometry.csv",
        "file_type": "csv",
        "mime_type": "text/csv",
        "file_size": 2450300,
        "thumbnail_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_geo_2025_02",
        "title": "Borehole Core Spectrometry & Element Assays Table",
        "description": "Tabular assays of 12,000 drill core samples measuring copper, gold, zinc, and iron sulfide ppm.",
        "tags": ["csv", "spectrometry", "mining", "assay", "core-sample", "drilling"],
        "category": "Nature",
        "content_summary": "CSV dataset detailing elemental concentration curves every 0.5 meters across 24 exploratory drill holes.",
        "ocr_text": "sample_id,depth_m,cu_pct,au_g_t,zn_pct,fe_pct,rock_type\nBH-01-001,0.5,0.42,0.12,0.85,12.4,basalt\nBH-01-002,1.0,0.88,0.34,1.20,15.1,quartz_vein",
        "transcript": None,
        "caption": "Structured tabular data representing ICP-MS chemical spectrometry readings for mineral explorations.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    
    # 2. Satellite & Vehicles (Vehicles / Technology)
    {
        "file_id": "file_sat_001",
        "dataset_id": "ds_satellite_002",
        "dataset_name": "Satellite Earth Observation & Topography",
        "file_name": "orbital_radar_glacier_melt.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 7120300,
        "width": 4096,
        "height": 4096,
        "thumbnail_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_sat_2025_03",
        "title": "Synthetic Aperture Radar (SAR) Polar Ice Velocity Map",
        "description": "Interferometric radar observation recording glacial shelf displacement and ice stream velocity at 10m resolution.",
        "tags": ["satellite", "sar", "radar", "glacier", "climate", "polar", "earth-observation"],
        "category": "Vehicles",
        "content_summary": "Sentinel-1 SAR interferogram showing glacier velocity gradient accelerating to 2.4 meters per day.",
        "ocr_text": "SENTINEL-1B INTERFEROMETRY POLAR ORBIT PASS 142 AZIMUTH 192.4 DEG DISPLACEMENT VELOCITY VECTOR 2.4M/DAY",
        "transcript": None,
        "caption": "A luminous blue and violet synthetic aperture radar mosaic showing glacial contours and oceanic fractures.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_sat_002",
        "dataset_id": "ds_satellite_002",
        "dataset_name": "Satellite Earth Observation & Topography",
        "file_name": "drone_aerial_wildfire_thermal.mp4",
        "file_type": "video",
        "mime_type": "video/mp4",
        "file_size": 48102900,
        "width": 1920,
        "height": 1080,
        "duration": 45.2,
        "thumbnail_url": "https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_sat_2025_03",
        "title": "Autonomous Drone Thermal FLIR Infrared Wildfire Progression",
        "description": "Aerial infrared thermal telemetry video capturing active fire perimeter expansion and hotspot temperature nodes.",
        "tags": ["drone", "thermal", "infrared", "video", "wildfire", "safety", "telemetry"],
        "category": "Vehicles",
        "content_summary": "FLIR thermal drone footage tracking wildfire hotspot containment line breach at 780°C peak infrared emission.",
        "ocr_text": "FLIR THERMAL CAMERA 640x512 T_MAX: 782C T_AVG: 310C DRONE_ALT: 400M HEADING: 045 SPEED: 18KM/H",
        "transcript": "Flight control, drone 4 is over Sector 9. Thermal imaging indicates perimeter advance along the western ridge. Hotspot intensity reaching 780 Celsius.",
        "caption": "High altitude thermal FLIR video displaying glowing orange wildfire perimeters contrasted against dark cool terrain.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },

    # 3. Industrial Safety & Equipment (Technology / People)
    {
        "file_id": "file_safe_001",
        "dataset_id": "ds_safety_003",
        "dataset_name": "Industrial Safety & Equipment Video Audits",
        "file_name": "crane_rigging_safety_briefing.mp3",
        "file_type": "audio",
        "mime_type": "audio/mp3",
        "file_size": 5291000,
        "duration": 182.5,
        "thumbnail_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1581092160607-ee22621dd758?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_safety_2025_01",
        "title": "Heavy Crane Lift Safety Protocol Briefing & Audio Audit",
        "description": "Shift supervisor audio recording instructing field engineers on tandem crane rigging, sling angles, and exclusion zones.",
        "tags": ["audio", "safety", "crane", "industrial", "protocol", "transcript", "inspection"],
        "category": "Technology",
        "content_summary": "Pre-shift safety meeting recording emphasizing 60-degree bridle sling angles and secondary emergency stop procedures.",
        "ocr_text": None,
        "transcript": "All rigging crews, verify the four-leg wire rope slings before the 40-ton turbine lift. Ensure tag lines are manned and nobody enters the swing radius. Wind speed is currently 8 knots, well below cutoff limits.",
        "caption": "Industrial voice recording detailing hazardous lifting operation safety requirements and emergency controls.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_safe_002",
        "dataset_id": "ds_safety_003",
        "dataset_name": "Industrial Safety & Equipment Video Audits",
        "file_name": "robot_arm_collision_avoidance.mp4",
        "file_type": "video",
        "mime_type": "video/mp4",
        "file_size": 39401200,
        "width": 1920,
        "height": 1080,
        "duration": 32.0,
        "thumbnail_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_safety_2025_02",
        "title": "Robotic Arm Computer Vision Safety Interlock Demo",
        "description": "Automated factory demonstration of optical LiDAR sensors halting 6-axis articulated manipulator upon worker proximity.",
        "tags": ["robot", "ai", "safety", "computer-vision", "automation", "manufacturing"],
        "category": "Technology",
        "content_summary": "Real-time AI spatial segmentation demo stopping robotic weld cycle within 8 milliseconds of perimeter breach.",
        "ocr_text": "SAFETY ZONE MONITOR: ACTIVE STATUS: OPERATIONAL VELOCITY: 2.2 M/S SPEED REDUCTION: 0.08S PROXIMITY ALERT 0.4M",
        "transcript": "Robot cell 3 safety interlock triggered. Motion paused instantly due to proximity detection. Resuming automated trajectory.",
        "caption": "Precision robotic welding arm executing swift maneuvers before pausing seamlessly as simulated technician approaches.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": True
    },

    # 4. Medical Pathology & Diagnostics (Medical)
    {
        "file_id": "file_med_001",
        "dataset_id": "ds_medical_004",
        "dataset_name": "Clinical Radiology & Pathology Imaging",
        "file_name": "chest_ct_nodule_segmentation.png",
        "file_type": "image",
        "mime_type": "image/png",
        "file_size": 3912000,
        "width": 2048,
        "height": 2048,
        "thumbnail_url": "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_med_2025_01",
        "title": "High-Resolution Axial Chest CT Scan with AI Nodule Segmentation",
        "description": "Contrast-enhanced helical computed tomography DICOM render highlighting 6mm ground-glass pulmonary opacity in right upper lobe.",
        "tags": ["medical", "radiology", "ct-scan", "pathology", "pulmonary", "ai-detection"],
        "category": "Medical",
        "content_summary": "Axial slice at T4 vertebra demonstrating AI-segmented 6.2mm subsolid nodule with 94.2% benign probability.",
        "ocr_text": "PATIENT_ANON_901 SLICE 184/512 KV 120 MA 240 WINDOW LUNG (W:1500 L:-600) AI CONFIDENCE 0.942 NODULE_VOL 142MM3",
        "transcript": None,
        "caption": "Axial medical CT radiograph displaying lung parenchyma with highlighted cyan bounding box around small pulmonary lesion.",
        "pii_detected": True,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_med_002",
        "dataset_id": "ds_medical_004",
        "dataset_name": "Clinical Radiology & Pathology Imaging",
        "file_name": "pathology_dictation_biopsy_case.wav",
        "file_type": "audio",
        "mime_type": "audio/wav",
        "file_size": 7200400,
        "duration": 210.0,
        "thumbnail_url": "https://images.unsplash.com/photo-1579154204601-01588f351e67?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1579154204601-01588f351e67?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_med_2025_01",
        "title": "Chief Pathologist Audio Dictation - Microscopic Biopsy Review",
        "description": "Audio transcription of histopathological analysis describing cellular morphology, mitosis rates, and surgical margins.",
        "tags": ["medical", "audio", "pathology", "biopsy", "transcript", "histology"],
        "category": "Medical",
        "content_summary": "Histologic evaluation notes uniform glandular architecture, low mitotic index, and clear surgical resection margins.",
        "ocr_text": None,
        "transcript": "Specimen A reveals well-differentiated squamous epithelium. The basal lamina is completely intact with no invasive stromal infiltration. Margins are widely clear by greater than 8 millimeters.",
        "caption": "Clinical audio recording of attending pathologist reading microscopic histological tissue slides.",
        "pii_detected": True,
        "nsfw_detected": False,
        "ai_generated": False
    },

    # 5. Architecture & Urban Planning (Architecture)
    {
        "file_id": "file_arch_001",
        "dataset_id": "ds_urban_006",
        "dataset_name": "Urban Architecture & BIM Structural Scans",
        "file_name": "cantilever_bridge_stress_cad.pdf",
        "file_type": "document",
        "mime_type": "application/pdf",
        "file_size": 11400200,
        "thumbnail_url": "https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_arch_2025_01",
        "title": "Cable-Stayed Steel Bridge Finite Element Structural Analysis",
        "description": "Engineering blueprint and stress vector calculations for 600m central span suspension pylon under aerodynamic wind shear.",
        "tags": ["architecture", "bridge", "cad", "blueprint", "engineering", "structural"],
        "category": "Architecture",
        "content_summary": "CAD drawing set and von Mises stress simulations confirming safety margin under category 4 hurricane vortex shedding.",
        "ocr_text": "STRUCTURAL DWG 402-A TENSION CABLE MATRIX T1-T32 HIGH-STRENGTH LOW-RELAXATION PRESTRESSED STRAND MAX TENSION 4200 KN",
        "transcript": None,
        "caption": "Complex architectural engineering blueprint with wireframe load-bearing stress lines and dimensional callouts.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_arch_002",
        "dataset_id": "ds_urban_006",
        "dataset_name": "Urban Architecture & BIM Structural Scans",
        "file_name": "futuristic_glass_skyscraper_concept.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 5890000,
        "width": 3000,
        "height": 4000,
        "thumbnail_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_arch_2025_02",
        "title": "Biophilic Skyscraper Concept with Vertical Forest Terraces",
        "description": "Generative architectural visualization of a 70-story helical skyscraper integrated with solar photovoltaic glass and native foliage.",
        "tags": ["architecture", "skyscraper", "ai-generated", "biophilic", "sustainable", "concept"],
        "category": "Architecture",
        "content_summary": "Concept design featuring double-curved parametric glass facade and cantilevered sky-gardens for zero-emission urban living.",
        "ocr_text": "NEXUS TOWER 2035 ELEVATION +320M SOLAR GLASS EFFICIENCY 22.4% RAINWATER RECAPTURE SYSTEM",
        "transcript": None,
        "caption": "Sleek modern glass skyscraper spiraling toward a clear sunset with lush green terraces clinging to every tenth tier.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": True
    },

    # 6. Animals & Wildlife (Animals)
    {
        "file_id": "file_anim_001",
        "dataset_id": "ds_wildlife_007",
        "dataset_name": "Global Wildlife & Biodiversity Acoustics",
        "file_name": "snow_leopard_camera_trap.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 6120400,
        "width": 4000,
        "height": 3000,
        "thumbnail_url": "https://images.unsplash.com/photo-1534188753412-3e26d0d618d6?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1534188753412-3e26d0d618d6?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_anim_2025_01",
        "title": "Himalayan Snow Leopard Mountain Ridgeline Motion Capture",
        "description": "High-resolution camera-trap photograph of an adult Panthera uncia navigating steep rocky mountain pass at 4,600m elevation.",
        "tags": ["animals", "wildlife", "camera-trap", "leopard", "biodiversity", "conservation"],
        "category": "Animals",
        "content_summary": "Night-vision sensor capture documenting healthy adult male snow leopard establishing scent territory in Ladakh range.",
        "ocr_text": "RECONYX CAM_14 2025-05-18 22:14:08 TEMP -6C LAT 34.152 LON 77.581 SENSOR TRIGGER 0.2S",
        "transcript": None,
        "caption": "A majestic snow leopard walking silently across moonlit craggy limestone rocks dusted with fresh powder snow.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_anim_002",
        "dataset_id": "ds_wildlife_007",
        "dataset_name": "Global Wildlife & Biodiversity Acoustics",
        "file_name": "humpback_whale_hydrophone_song.mp3",
        "file_type": "audio",
        "mime_type": "audio/mp3",
        "file_size": 8900000,
        "duration": 294.0,
        "thumbnail_url": "https://images.unsplash.com/photo-1568430462989-44163eb1752f?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1568430462989-44163eb1752f?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_anim_2025_01",
        "title": "Deep Ocean Hydrophone Acoustic Recording - Humpback Whale Mating Chants",
        "description": "Calibrated underwater hydrophone audio capture featuring multi-octave harmonic vocalizations of North Pacific humpback whales.",
        "tags": ["animals", "audio", "whale", "marine", "hydrophone", "bioacoustics", "ocean"],
        "category": "Animals",
        "content_summary": "Underwater audio recording recording complex repeating stanzas of low frequency groans and high-pitched chirps.",
        "ocr_text": None,
        "transcript": "Vocal sequence 4B identified. Fundamental frequency ranges between 30 Hz and 4 kHz with prominent 3rd harmonic resonance.",
        "caption": "Haunting and resonant underwater bioacoustic recording of whale song echoing through the open pelagic depths.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },

    # 7. Renewable Energy & Technology (Technology)
    {
        "file_id": "file_tech_001",
        "dataset_id": "ds_energy_008",
        "dataset_name": "Renewable Wind & Solar Telemetry Logs",
        "file_name": "wind_turbine_bearing_vibration.csv",
        "file_type": "csv",
        "mime_type": "text/csv",
        "file_size": 3810000,
        "thumbnail_url": "https://images.unsplash.com/photo-1466611653911-95081537e5b7?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1466611653911-95081537e5b7?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_energy_2025_01",
        "title": "3.6MW Offshore Wind Turbine Main Bearing Accelerometer Telemetry",
        "description": "Triaxial high-frequency vibration sensor log monitoring planetary gearbox and pitch drive bearing health.",
        "tags": ["technology", "csv", "wind-turbine", "vibration", "sensor", "telemetry", "energy"],
        "category": "Technology",
        "content_summary": "Timeseries vibration spectrum over 100 operating hours showing healthy harmonic signatures without inner race fault peaks.",
        "ocr_text": "timestamp,rpm,vib_x_g,vib_y_g,vib_z_g,bearing_temp_c,power_kw\n2025-06-01T00:00:01,14.8,0.12,0.14,0.08,54.2,3420\n2025-06-01T00:00:02,14.9,0.11,0.15,0.09,54.2,3450",
        "transcript": None,
        "caption": "Structured CSV dataset tracking triaxial vibration acceleration amplitudes and generator power output.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_tech_002",
        "dataset_id": "ds_safety_003",
        "dataset_name": "Industrial Safety & Equipment Video Audits",
        "file_name": "safety_compliance_inspection_protocol.pdf",
        "file_type": "document",
        "mime_type": "application/pdf",
        "file_size": 6420100,
        "thumbnail_url": "https://images.unsplash.com/photo-1450133064473-71024230f91b?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1450133064473-71024230f91b?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_safety_2025_02",
        "title": "OSHA High-Voltage Substation Safety & Lockout-Tagout Manual",
        "description": "Comprehensive operational manual outlining isolation verification, arc flash boundary PPE, and grounding protocols.",
        "tags": ["document", "safety", "protocol", "compliance", "inspection", "audit"],
        "category": "Business",
        "content_summary": "Standard operating guidelines for 115kV transmission substation maintenance and zero-energy verification.",
        "ocr_text": "LOCKOUT TAGOUT (LOTO) STANDARD PROCEDURE 8.4 VERIFY DE-ENERGIZATION USING TESTER TEST-BEFORE-TOUCH GROUNDING CLAMPS INSTALLED",
        "transcript": None,
        "caption": "Detailed regulatory compliance PDF manual complete with safety hazard checklists and warning placards.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },

    # 8. People, Education, Business, Sports, Food, Abstract
    {
        "file_id": "file_peop_001",
        "dataset_id": "ds_safety_003",
        "dataset_name": "Industrial Safety & Equipment Video Audits",
        "file_name": "engineers_collaborative_war_room.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 4900200,
        "width": 3840,
        "height": 2560,
        "thumbnail_url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_peop_2025_01",
        "title": "Software Engineering Team Architecture Review Meeting",
        "description": "Team of senior AI developers and systems architects whiteboarding distributed microservice data pipelines.",
        "tags": ["people", "business", "technology", "team", "engineer", "software", "meeting"],
        "category": "People",
        "content_summary": "Collaborative workshop session analyzing query latency reduction across multimodal vector search nodes.",
        "ocr_text": "HYBRID SEARCH ARCHITECTURE RRF K=60 QDRANT VECTOR POSTGRES FTS LATENCY < 45MS",
        "transcript": None,
        "caption": "A diverse group of technology professionals enthusiastically discussing diagrams on a luminous glass whiteboard.",
        "pii_detected": True,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_food_001",
        "dataset_id": "ds_geological_001",
        "dataset_name": "Geological Survey & Mineral Maps 2025",
        "file_name": "smart_agriculture_multispectral_crop_health.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 5120300,
        "width": 3600,
        "height": 2400,
        "thumbnail_url": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_food_2025_01",
        "title": "Multispectral NDVI Precision Agriculture Crop Health Survey",
        "description": "Normalized Difference Vegetation Index (NDVI) orbital scan assessing wheat canopy vigor and moisture deficit.",
        "tags": ["food", "agriculture", "crop", "ndvi", "satellite", "harvest", "nature"],
        "category": "Food",
        "content_summary": "Precision agricultural map highlighting high chlorophyll reflectance (NDVI 0.82) across center-pivot irrigated fields.",
        "ocr_text": "NDVI INDEX 0.82 VIGOROUS CANOPY SOIL MOISTURE 28% ESTIMATED YIELD 4.8 TONS/HECTARE",
        "transcript": None,
        "caption": "Vibrant emerald green and gold aerial view of circular agricultural farm fields mapped by satellite sensor.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_sports_001",
        "dataset_id": "ds_autonomous_005",
        "dataset_name": "Autonomous Navigation & Telemetry Corpus",
        "file_name": "biomechanics_sprinter_high_speed_tracking.mp4",
        "file_type": "video",
        "mime_type": "video/mp4",
        "file_size": 28400100,
        "width": 1920,
        "height": 1080,
        "duration": 24.5,
        "thumbnail_url": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_sports_2025_01",
        "title": "Olympic 100m Sprinter High-Speed Biomechanics 3D Kinematics",
        "description": "500 FPS motion capture tracking joint flexion angles, ground contact time, and horizontal force vector propulsions.",
        "tags": ["sports", "video", "athlete", "biomechanics", "kinematics", "running"],
        "category": "Sports",
        "content_summary": "High-speed kinematic video displaying skeleton overlay with 0.088s ground contact time during maximum velocity phase.",
        "ocr_text": "GROUND CONTACT TIME: 0.088S STRIDE FREQ: 4.8HZ KNEE EXTENSION ANGLE: 168 DEG PEAK HORIZONTAL FORCE: 1420N",
        "transcript": "Biomechanics data logged. Athlete achieved peak horizontal velocity of 11.8 meters per second at the 60-meter split.",
        "caption": "Slow-motion video of an elite track sprinter exploding out of starting blocks with digital skeletal telemetry lines.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    },
    {
        "file_id": "file_abst_001",
        "dataset_id": "ds_geological_001",
        "dataset_name": "Geological Survey & Mineral Maps 2025",
        "file_name": "fractal_quantum_wavefunction_density.jpg",
        "file_type": "image",
        "mime_type": "image/jpeg",
        "file_size": 6800100,
        "width": 3840,
        "height": 2160,
        "thumbnail_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_abst_2025_01",
        "title": "Quantum Wavefunction Interference Pattern & Fractal Geometry",
        "description": "Mathematical simulation of quantum harmonic oscillator probability densities rendered in chromatic iridescent hues.",
        "tags": ["abstract", "quantum", "mathematics", "geometry", "pattern", "ai-generated"],
        "category": "Abstract",
        "content_summary": "High-dimensional manifold projection illustrating wave interference and topological boundary knots.",
        "ocr_text": "PSI(X,Y,Z) PROBABILITY AMPLITUDE TOPOLOGICAL WINDING NUMBER N=7 ENERGY EIGENVALUE E_0",
        "transcript": None,
        "caption": "Hypnotic psychedelic fractal geometry blending swirling neon purple, blue, and gold volumetric tendrils.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": True
    },
    {
        "file_id": "file_edu_001",
        "dataset_id": "ds_urban_006",
        "dataset_name": "Urban Architecture & BIM Structural Scans",
        "file_name": "machine_learning_curriculum_syllabus.pdf",
        "file_type": "document",
        "mime_type": "application/pdf",
        "file_size": 3410200,
        "thumbnail_url": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=600&auto=format&fit=crop&q=80",
        "preview_url": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=1600&auto=format&fit=crop&q=80",
        "source_batch": "batch_edu_2025_01",
        "title": "Advanced Multimodal Machine Learning & Vector Search Syllabus",
        "description": "University graduate course curriculum covering contrastive representation learning, RRF ranking, and vector indexing.",
        "tags": ["education", "document", "syllabus", "machine-learning", "learning", "study"],
        "category": "Education",
        "content_summary": "Academic course outline covering contrastive pre-training (CLIP), approximate nearest neighbor search (HNSW), and Reciprocal Rank Fusion.",
        "ocr_text": "CS-889 MULTIMODAL INFORMATION RETRIEVAL LECTURE 4: RECIPROCAL RANK FUSION (RRF) AND EMBEDDING PROJECTIONS PREREQUISITES: LINEAR ALGEBRA",
        "transcript": None,
        "caption": "Structured university lecture curriculum document featuring module outlines, reading lists, and lab exercises.",
        "pii_detected": False,
        "nsfw_detected": False,
        "ai_generated": False
    }
]

async def seed_database():
    print("Starting database and vector index seeding...")
    await init_db()
    init_qdrant()
    qdrant = get_qdrant_client()
    embedder = get_embedding_client()

    async with AsyncSessionLocal() as session:
        # Seed Datasets
        for d in DATASETS_DATA:
            existing = await session.get(Dataset, d["id"])
            if not existing:
                dataset = Dataset(
                    id=d["id"],
                    name=d["name"],
                    description=d["description"],
                    category=d["category"],
                    file_count=15,
                    total_size_bytes=1024 * 1024 * 350,
                    thumbnail_url=d["thumbnail_url"],
                    view_count=d["view_count"],
                    download_count=d["download_count"],
                    search_hit_count=d["search_hit_count"],
                    popularity_score=d["popularity_score"],
                    created_at=datetime.now(timezone.utc) - timedelta(days=20)
                )
                session.add(dataset)
        await session.commit()
        print(f"Seeded {len(DATASETS_DATA)} datasets into PostgreSQL/SQLite.")

        # Seed Files
        qdrant_points = []
        for f in FILES_DATA:
            existing = await session.get(FileMetadata, f["file_id"])
            if not existing:
                checksum = hashlib.sha256(f["file_name"].encode()).hexdigest()
                file_obj = FileMetadata(
                    file_id=f["file_id"],
                    dataset_id=f["dataset_id"],
                    dataset_name=f["dataset_name"],
                    file_name=f["file_name"],
                    file_type=f["file_type"],
                    mime_type=f["mime_type"],
                    file_size=f["file_size"],
                    width=f.get("width"),
                    height=f.get("height"),
                    duration=f.get("duration"),
                    thumbnail_url=f.get("thumbnail_url"),
                    preview_url=f.get("preview_url"),
                    source_batch=f.get("source_batch"),
                    checksum=checksum,
                    title=f["title"],
                    description=f.get("description"),
                    tags=f.get("tags", []),
                    category=f["category"],
                    content_summary=f.get("content_summary"),
                    ocr_text=f.get("ocr_text"),
                    transcript=f.get("transcript"),
                    caption=f.get("caption"),
                    pii_detected=f.get("pii_detected", False),
                    nsfw_detected=f.get("nsfw_detected", False),
                    ai_generated=f.get("ai_generated", False),
                    embedding_model="clip-ViT-B-32",
                    embedding_version="v1.0",
                    embedding_status="INDEXED",
                    download_count=18,
                    file_preview_count=45,
                    ingested_at=datetime.now(timezone.utc) - timedelta(days=3)
                )
                session.add(file_obj)

            # Generate embedding for Qdrant index
            doc_text = f"{f['title']} {f['category']} {f.get('description', '')} {f.get('caption', '')} {' '.join(f.get('tags', []))} {f.get('ocr_text', '')} {f.get('transcript', '')}"
            vector = embedder.generate_text_embedding(doc_text)
            
            qdrant_points.append(
                qmodels.PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f["file_id"])),
                    vector=vector,
                    payload={
                        "file_id": f["file_id"],
                        "dataset_id": f["dataset_id"],
                        "dataset_name": f["dataset_name"],
                        "file_name": f["file_name"],
                        "file_type": f["file_type"],
                        "category": f["category"],
                        "title": f["title"],
                        "ai_generated": f.get("ai_generated", False),
                        "pii_detected": f.get("pii_detected", False),
                        "tags": f.get("tags", [])
                    }
                )
            )

        await session.commit()
        print(f"Seeded {len(FILES_DATA)} files into SQL database.")

        # Index vectors into Qdrant
        if qdrant_points:
            qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                points=qdrant_points
            )
            print(f"Indexed {len(qdrant_points)} vectors into Qdrant collection '{settings.QDRANT_COLLECTION_NAME}'.")

        # Seed sample search events for trending
        sample_queries = [
            ("coal mining", "Nature", 14),
            ("satellite earth observation", "Vehicles", 22),
            ("lithium mineral map", "Nature", 18),
            ("industrial safety protocol", "Technology", 16),
            ("robotic arm computer vision", "Technology", 12),
            ("humpback whale audio", "Animals", 10),
            ("chest ct scan nodule", "Medical", 15),
            ("skyscraper architecture", "Architecture", 8),
            ("wind turbine vibration", "Technology", 9)
        ]
        for query_str, cat, count in sample_queries:
            for _ in range(count):
                event = SearchEvent(
                    event_type="SEARCH",
                    query=query_str,
                    normalized_query=query_str.lower(),
                    user_id="usr_demo_eval",
                    user_role="ANALYST",
                    result_count=8,
                    created_at=datetime.now(timezone.utc) - timedelta(hours=2)
                )
                session.add(event)
        await session.commit()
        print("Seeded sample search events for trending search feature.")

if __name__ == "__main__":
    asyncio.run(seed_database())
