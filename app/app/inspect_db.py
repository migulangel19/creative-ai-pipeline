
import sqlite3

# Conecta a la base de datos
conn = sqlite3.connect("memory.db")
cursor = conn.cursor()

# Muestra las tablas disponibles
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tablas:", cursor.fetchall())

# Consulta las primeras filas de la tabla "memories"
cursor.execute("SELECT * FROM memories LIMIT 5;")
for row in cursor.fetchall():
    print(row)

conn.close()
