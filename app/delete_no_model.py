import sqlite3

# Ruta de la base de datos
db_path = "memory.db"

# Conecta a la base de datos
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Elimina registros sin modelo 3D
cursor.execute("DELETE FROM memories WHERE model_path = 'none'")
conn.commit()

# Imprime cuántas filas fueron eliminadas
print(f"{cursor.rowcount} memorias sin modelo 3D eliminadas.")

conn.close()
