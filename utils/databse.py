import sqlite3
from sqlite3 import Error
import config
from datetime import datetime

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        return conn
    except Error as e:
        print(f"Database error: {e}")
    return conn

def initialize_database():
    commands = [
        """CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            yt_verify_channel INTEGER,
            yt_verify_role INTEGER,
            suggestions_channel INTEGER,
            level_channel INTEGER,
            ai_channel INTEGER,
            yt_notify_channel INTEGER
        )""",
        """CREATE TABLE IF NOT EXISTS youtube_channels (
            channel_id TEXT PRIMARY KEY,
            guild_id INTEGER,
            last_video_id TEXT,
            FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
        )""",
        """CREATE TABLE IF NOT EXISTS suggestions (
            message_id INTEGER PRIMARY KEY,
            guild_id INTEGER,
            author_id INTEGER,
            content TEXT,
            upvotes INTEGER DEFAULT 0,
            downvotes INTEGER DEFAULT 0,
            FOREIGN KEY (guild_id) REFERENCES guilds (guild_id)
        )""",
        """CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER,
            guild_id INTEGER,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            last_message TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        )""",
        """CREATE TABLE IF NOT EXISTS votes (
            user_id INTEGER,
            suggestion_id INTEGER,
            vote_type INTEGER,  -- 1 for upvote, -1 for downvote
            PRIMARY KEY (user_id, suggestion_id)
        )""",
        """CREATE TABLE IF NOT EXISTS yt_verifications (
            user_id INTEGER,
            guild_id INTEGER,
            status TEXT,  -- 'pending', 'approved', 'rejected'
            proof_url TEXT,
            timestamp TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        )"""
    ]
    
    conn = create_connection()
    if conn is not None:
        try:
            c = conn.cursor()
            for command in commands:
                c.execute(command)
            conn.commit()
        except Error as e:
            print(f"Error initializing database: {e}")
        finally:
            conn.close()

initialize_database()

# Database helper functions
def get_guild_config(guild_id):
    conn = create_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT * FROM guilds WHERE guild_id=?", (guild_id,))
        return c.fetchone()
    except Error as e:
        print(f"Error getting guild config: {e}")
        return None
    finally:
        conn.close()

def update_guild_config(guild_id, **kwargs):
    conn = create_connection()
    try:
        c = conn.cursor()
        
        # Check if guild exists
        c.execute("SELECT 1 FROM guilds WHERE guild_id=?", (guild_id,))
        exists = c.fetchone()
        
        if exists:
            # Update existing record
            set_clause = ", ".join([f"{key}=?" for key in kwargs.keys()])
            values = tuple(kwargs.values()) + (guild_id,)
            c.execute(f"UPDATE guilds SET {set_clause} WHERE guild_id=?", values)
        else:
            # Insert new record
            columns = ["guild_id"] + list(kwargs.keys())
            placeholders = ", ".join(["?"] * len(columns))
            values = (guild_id,) + tuple(kwargs.values())
            c.execute(f"INSERT INTO guilds ({', '.join(columns)}) VALUES ({placeholders})", values)
        
        conn.commit()
    except Error as e:
        print(f"Error updating guild config: {e}")
    finally:
        conn.close()