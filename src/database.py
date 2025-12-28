import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import sys
sys.path.append('..')
from config.config import config

class Database:
    def __init__(self):
        self.conn = psycopg2.connect(config.DATABASE_URL)
        self.create_tables()

    def create_tables(self):
        """Create database schema"""
        cursor = self.conn.cursor()

        # Opportunities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                token_in VARCHAR(50),
                token_out VARCHAR(50),
                buy_dex VARCHAR(50),
                sell_dex VARCHAR(50),
                buy_price DECIMAL(20,8),
                sell_price DECIMAL(20,8),
                profit_pct DECIMAL(10,4),
                profit_usd DECIMAL(10,2),
                amount DECIMAL(20,8),
                executed BOOLEAN DEFAULT FALSE
            )
        """)

        # Executions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id SERIAL PRIMARY KEY,
                opportunity_id INTEGER REFERENCES opportunities(id),
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tx_hash VARCHAR(66),
                success BOOLEAN,
                actual_profit_usd DECIMAL(10,2),
                gas_used INTEGER,
                gas_price_gwei DECIMAL(10,4),
                error_message TEXT
            )
        """)

        # Gas prices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gas_prices (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                gas_price_gwei DECIMAL(10,4),
                network VARCHAR(20)
            )
        """)

        self.conn.commit()
        cursor.close()
        print("✅ Database tables created successfully")

    def insert_opportunity(self, opp):
        """Insert opportunity into database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO opportunities
            (token_in, token_out, buy_dex, sell_dex, buy_price, sell_price, profit_pct, profit_usd, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            opp['token_in'], opp['token_out'], opp['buy_dex'], opp['sell_dex'],
            opp['buy_price'], opp['sell_price'], opp['profit_pct'], opp['profit_usd'], opp['amount']
        ))
        opp_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()
        return opp_id

    def get_unexecuted_opportunities(self):
        """Get all unexecuted profitable opportunities"""
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM opportunities
            WHERE executed = FALSE AND profit_pct >= %s
            ORDER BY profit_pct DESC
        """, (config.PROFIT_THRESHOLD * 100,))
        results = cursor.fetchall()
        cursor.close()
        return results

if __name__ == "__main__":
    db = Database()
    print("Database initialized!")
