-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    group_code TEXT,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица групп
CREATE TABLE IF NOT EXISTS groups (
    group_code TEXT PRIMARY KEY,
    teacher_telegram_id INTEGER,
    FOREIGN KEY (teacher_telegram_id) REFERENCES users(telegram_id)
);

-- Таблица расписания
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_code TEXT NOT NULL,
    weekday TEXT NOT NULL,
    time TEXT NOT NULL,
    subject TEXT NOT NULL,
    FOREIGN KEY (group_code) REFERENCES groups(group_code)
);

-- Таблица оценок
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    date TEXT NOT NULL,
    grade INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(telegram_id)
);

-- Таблица уведомлений
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    notification_type TEXT DEFAULT 'general',
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
);

-- Таблица истории изменений расписания
CREATE TABLE IF NOT EXISTS schedule_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER,
    group_code TEXT NOT NULL,
    change_type TEXT NOT NULL, -- 'add', 'update', 'delete'
    weekday TEXT,
    time TEXT,
    subject TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id)
);

-- Таблица посещаемости
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,       -- ID студента (внешний ключ к таблице пользователей)
    subject TEXT NOT NULL,             -- Название предмета
    qr_timestamp TEXT NOT NULL,        -- Время из QR-кода (метка сессии, ISO формат)
    submission_timestamp TEXT NOT NULL,-- Время фактической отметки студентом (ISO формат)
    status TEXT NOT NULL,              -- Статус: 'PRESENT', 'ERROR_EXPIRED', 'ERROR_DUPLICATE', 'ERROR_GROUP_MISMATCH', 'ERROR_INVALID_QR'
    group_id INTEGER,                  -- ID группы из QR-кода (для сверки и отчетности)
    FOREIGN KEY (student_id) REFERENCES users(telegram_id)
);