import sqlite3
import os

class Database:
    def __init__(self, db_path='literacy_system.db'):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def create_tables(self):
        conn = self.connect()
        cursor = conn.cursor()
        
        # 创建vocabulary表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER NOT NULL,
            unit INTEGER NOT NULL,
            content TEXT NOT NULL,
            pinyin TEXT,
            type TEXT NOT NULL,  -- 生词、古诗、成语等
            difficulty INTEGER NOT NULL,  -- 1-5级
            knowledge_unit TEXT NOT NULL
        )
        ''')
        
        # 创建learning_progress表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            vocabulary_id INTEGER NOT NULL,
            proficiency_level INTEGER DEFAULT 0,  -- 0-5级
            last_review_date TEXT,
            review_interval INTEGER DEFAULT 1,  -- 天数
            review_count INTEGER DEFAULT 0,
            ease_factor REAL DEFAULT 2.5,
            error_count INTEGER DEFAULT 0,
            last_error_type TEXT,  -- 字形错误、拼音错误、漏写、顺序错误
            FOREIGN KEY (vocabulary_id) REFERENCES vocabulary (id)
        )
        ''')
        
        # 创建records表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            vocabulary_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            result BOOLEAN NOT NULL,  -- 正确/错误
            error_type TEXT,  -- 字形错误、拼音错误、漏写、顺序错误
            time_used INTEGER,  -- 用时（秒）
            FOREIGN KEY (vocabulary_id) REFERENCES vocabulary (id)
        )
        ''')
        
        conn.commit()
        self.close()
    
    def check_tables(self):
        conn = self.connect()
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        self.close()
        return table_names

if __name__ == "__main__":
    db = Database()
    db.create_tables()
    print("数据库表创建完成")
    print("现有表:", db.check_tables())
