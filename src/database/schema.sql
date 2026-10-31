CREATE TABLE patients (
  patient_id         TEXT PRIMARY KEY,          -- 'usr-anon-<random suffix>', never derived from PII
  preferred_name     TEXT,                      -- PII: entered by the doctor, never sent to NER/API
  birth_date         TEXT,
  phone              TEXT,
  email              TEXT,
  preferred_channel  TEXT,
  emergency_name     TEXT,
  emergency_relation TEXT,
  emergency_phone    TEXT,
  emergency_consent  INTEGER CHECK (emergency_consent IN (0,1)),
  created_at         TEXT NOT NULL
);
CREATE TABLE sessions (
  session_id         TEXT PRIMARY KEY,          -- UUID
  patient_id         TEXT NOT NULL REFERENCES patients,
  session_number     INTEGER NOT NULL,          -- max+1 per patient; 1 = first visit
  session_date       TEXT NOT NULL,             -- YYYY-MM-DD
  audio_path         TEXT NOT NULL,             -- two-channel recording
  patient_audio_path TEXT,                      -- patient.wav, written by the Audio Transcription system
  channel_map        TEXT NOT NULL DEFAULT '{"DOCTOR":0,"PATIENT":1}',
  language           TEXT,                      -- 'uk' | 'en'
  transcript_meta    TEXT,                      -- JSON: duration and speaking time metadata from the Audio Transcription system
  ner_map            TEXT,                      -- JSON map; stored locally only
  status             TEXT NOT NULL DEFAULT 'uploaded'      -- last COMPLETED pipeline step
                     CHECK (status IN ('uploaded','transcribed','sanitized','analyzed','drafted','approved')),
  failed_step        TEXT,                      -- failed step (NULL when there is no error)
  error              TEXT,                      -- error message; both fields are cleared after a successful retry
  created_at         TEXT NOT NULL,
  UNIQUE (patient_id, session_number)
);
CREATE TABLE transcript_segments (
  session_id     TEXT NOT NULL REFERENCES sessions,
  segment_id         INTEGER NOT NULL,              -- starts at 0, ordered by start_time
  speaker        TEXT NOT NULL CHECK (speaker IN ('DOCTOR','PATIENT')),
  start_time         REAL NOT NULL,                 -- seconds from the beginning of the recording
  end_time       REAL NOT NULL,
  text_raw           TEXT NOT NULL,                 -- contains PII, stored locally only
  text_sanitized     TEXT,                          -- after NER; the only text sent to external APIs
  confidence     REAL,
  PRIMARY KEY (session_id, segment_id)
);
CREATE TABLE biomarkers (
  session_id TEXT PRIMARY KEY REFERENCES sessions,
  data       TEXT NOT NULL CHECK (json_valid(data))     -- complete output from the Biomarker Extraction system
);
CREATE TABLE medical_cards (
  patient_id        TEXT PRIMARY KEY REFERENCES patients,   -- one card per patient
  source_session_id TEXT NOT NULL REFERENCES sessions,      -- source session
  status            TEXT NOT NULL DEFAULT 'generated'
                    CHECK (status IN ('generated','draft','approved')),  -- generated: raw output with placeholders; draft: after restore
  draft             TEXT CHECK (json_valid(draft)),         -- restored output from the Clinical Card Generation system; NULL when disabled
  data              TEXT CHECK (json_valid(data)),          -- working card: generated fields, doctor fields, and edits
  review_started_at TEXT,
  approved_at       TEXT
);
CREATE TABLE soap_notes (
  session_id        TEXT PRIMARY KEY REFERENCES sessions,   -- one note per session
  status            TEXT NOT NULL DEFAULT 'generated'
                    CHECK (status IN ('generated','draft','approved')),  -- generated: raw output with placeholders; draft: after restore
  draft             TEXT CHECK (json_valid(draft)),         -- restored output from the SOAP Note Generation system, not edited
  final             TEXT CHECK (json_valid(final)),         -- working SOAP note with doctor edits
  review_started_at TEXT,
  approved_at       TEXT
);