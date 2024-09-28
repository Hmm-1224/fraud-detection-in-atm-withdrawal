import sqlite3

# Function to connect to the database
def get_db_connection():
    return sqlite3.connect('atm_system.db')

# Create the users table
def create_users_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            customer_id TEXT NOT NULL UNIQUE,
            phone_number TEXT NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            debited_amount REAL NOT NULL DEFAULT 0,
            face_data BLOB NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Users table created successfully!")

if __name__ == '__main__':
    create_users_table()

