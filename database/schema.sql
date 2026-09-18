PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS emergencies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    location TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    severity INTEGER NOT NULL DEFAULT 0,
    people_affected INTEGER NOT NULL DEFAULT 0,
    injured INTEGER NOT NULL DEFAULT 0,
    critical_injured INTEGER NOT NULL DEFAULT 0,
    urgency INTEGER NOT NULL DEFAULT 0,
    reported_time TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL DEFAULT 0,
    available_quantity INTEGER NOT NULL DEFAULT 0,
    latitude REAL,
    longitude REAL,
    location TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'AVAILABLE',
    capacity INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id INTEGER NOT NULL,
    resource_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    priority_score REAL DEFAULT 0,
    eta_minutes REAL,
    allocation_reason TEXT,
    status TEXT NOT NULL DEFAULT 'RECOMMENDED',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    approved_at TEXT,
    FOREIGN KEY (emergency_id) REFERENCES emergencies(id) ON DELETE SET NULL,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS response_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    emergency_id INTEGER,
    resource_id INTEGER,
    action TEXT,
    old_status TEXT,
    new_status TEXT,
    notes TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (emergency_id) REFERENCES emergencies(id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emergencies_status ON emergencies(status);
CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON response_history(timestamp);