"""O script banco/criar_banco.sql precisa criar exatamente as tabelas descritas em app/db.py.

Só roda quando os testes usam um PostgreSQL (variável DATABASE_URL_TESTES); no SQLite é pulado.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.db import Base, engine

SCRIPT = Path(__file__).resolve().parents[2] / "banco" / "criar_banco.sql"

pytestmark = pytest.mark.skipif(engine.dialect.name != "postgresql", reason="o script é para PostgreSQL")


def _estrutura(conexao, schema: str) -> dict:
    inspetor = inspect(conexao)
    estrutura = {}
    for tabela in Base.metadata.sorted_tables:
        nome = tabela.name
        estrutura[nome] = {
            "colunas": sorted(
                (coluna["name"], str(coluna["type"]), coluna["nullable"])
                for coluna in inspetor.get_columns(nome, schema=schema)
            ),
            "chave_primaria": inspetor.get_pk_constraint(nome, schema=schema)["constrained_columns"],
            "chaves_estrangeiras": sorted(
                (fk["constrained_columns"], fk["referred_table"], fk["referred_columns"], fk["options"].get("ondelete"))
                for fk in inspetor.get_foreign_keys(nome, schema=schema)
            ),
            "unicas": sorted(sorted(u["column_names"]) for u in inspetor.get_unique_constraints(nome, schema=schema)),
            "indices": sorted(
                (indice["name"], indice["column_names"], indice["unique"])
                for indice in inspetor.get_indexes(nome, schema=schema)
            ),
            "checks": sorted(check["name"] for check in inspetor.get_check_constraints(nome, schema=schema)),
        }
    return estrutura


def test_script_cria_as_mesmas_tabelas_do_backend():
    script = SCRIPT.read_text(encoding="utf-8")
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conexao:
        psycopg = conexao.connection.driver_connection
        try:
            for schema in ("teste_script", "teste_orm"):
                psycopg.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                psycopg.execute(f"CREATE SCHEMA {schema}")

            psycopg.execute("SET search_path TO teste_script")
            psycopg.execute(script)
            psycopg.execute(script)  # rodar de novo não pode dar erro nem duplicar nada
            psycopg.execute("RESET search_path")

            Base.metadata.create_all(conexao.execution_options(schema_translate_map={None: "teste_orm"}))

            assert _estrutura(conexao, "teste_script") == _estrutura(conexao, "teste_orm")
        finally:
            psycopg.execute("RESET search_path")
            for schema in ("teste_script", "teste_orm"):
                psycopg.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
