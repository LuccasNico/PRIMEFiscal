import os
import tempfile

# Banco temporário para os testes (definido antes de importar a aplicação)
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.mkdtemp(), 'teste.db')}"
