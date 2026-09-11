import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.logging import get_logger
from app.metadata.models import (
    BusinessRule,
    Column,
    EnumValue,
    MetadataEmbedding,
    Relationship,
    Synonym,
    SyntheticExample,
    Table,
)
from app.metadata.schemas import (
    BusinessRuleContext,
    BusinessRuleCreate,
    ColumnCreate,
    EnumValueContext,
    EnumValueCreate,
    MatchedKeyword,
    RelationshipContext,
    RelationshipCreate,
    SynonymCreate,
    TableCreate,
)

logger = get_logger(__name__)

# Sentinela: métodos de leitura aceitam connection_id opcional. Quando None, não
# filtram por conexão (usado em testes e em contextos legados de conexão única).
_ConnId = uuid.UUID | None


class MetadataRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------ writes

    async def upsert_table(self, connection_id: uuid.UUID, table: TableCreate) -> Table:
        stmt = (
            insert(Table)
            .values(
                connection_id=connection_id,
                table_name=table.table_name,
                schema_name=table.schema_name,
                description=table.description,
                row_count=table.row_count,
            )
            .on_conflict_do_update(
                index_elements=["connection_id", "table_name"],
                set_={
                    "schema_name": table.schema_name,
                    "description": table.description,
                    "row_count": table.row_count,
                },
            )
            .returning(Table)
        )
        # populate_existing: sem isso, uma linha já no identity map (upsert anterior na
        # mesma sessão) fica com atributos antigos em cache em vez do UPDATE do upsert.
        result = await self.session.execute(stmt.execution_options(populate_existing=True))
        return result.scalar_one()

    async def upsert_column(self, table_id: uuid.UUID, column: ColumnCreate) -> Column:
        existing = await self.session.execute(
            select(Column).where(Column.table_id == table_id, Column.column_name == column.column_name)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            row.data_type = column.data_type
            row.is_nullable = column.is_nullable
            row.is_primary_key = column.is_primary_key
            row.is_foreign_key = column.is_foreign_key
            row.description = column.description
            row.sample_values = column.sample_values
            await self.session.flush()
            return row

        new_column = Column(
            table_id=table_id,
            column_name=column.column_name,
            data_type=column.data_type,
            is_nullable=column.is_nullable,
            is_primary_key=column.is_primary_key,
            is_foreign_key=column.is_foreign_key,
            description=column.description,
            sample_values=column.sample_values,
        )
        self.session.add(new_column)
        await self.session.flush()
        return new_column

    async def add_relationship(
        self,
        connection_id: uuid.UUID,
        source_table_id: uuid.UUID,
        target_table_id: uuid.UUID,
        relationship: RelationshipCreate,
    ) -> Relationship:
        new_relationship = Relationship(
            connection_id=connection_id,
            source_table_id=source_table_id,
            target_table_id=target_table_id,
            source_column=relationship.source_column,
            target_column=relationship.target_column,
            constraint_name=relationship.constraint_name,
        )
        self.session.add(new_relationship)
        await self.session.flush()
        return new_relationship

    async def add_synonym(self, connection_id: uuid.UUID, synonym: SynonymCreate) -> Synonym:
        new_synonym = Synonym(
            connection_id=connection_id,
            entity_type=synonym.entity_type,
            entity_id=synonym.entity_id,
            synonym=synonym.synonym,
            language=synonym.language,
        )
        self.session.add(new_synonym)
        await self.session.flush()
        return new_synonym

    async def add_business_rule(
        self, connection_id: uuid.UUID, table_id: uuid.UUID | None, rule: BusinessRuleCreate
    ) -> BusinessRule:
        new_rule = BusinessRule(
            connection_id=connection_id,
            table_id=table_id,
            rule_text=rule.rule_text,
            rule_type=rule.rule_type,
        )
        self.session.add(new_rule)
        await self.session.flush()
        return new_rule

    async def add_enum_value(
        self, connection_id: uuid.UUID, column_id: uuid.UUID, enum_value: EnumValueCreate
    ) -> EnumValue:
        new_enum_value = EnumValue(
            connection_id=connection_id,
            column_id=column_id,
            stored_value=enum_value.stored_value,
            display_label=enum_value.display_label,
            description=enum_value.description,
        )
        self.session.add(new_enum_value)
        await self.session.flush()
        return new_enum_value

    async def add_embedding(
        self,
        connection_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        content_text: str,
        embedding: list[float],
    ) -> MetadataEmbedding:
        new_embedding = MetadataEmbedding(
            connection_id=connection_id,
            source_type=source_type,
            source_id=source_id,
            content_text=content_text,
            embedding=embedding,
        )
        self.session.add(new_embedding)
        await self.session.flush()
        return new_embedding

    async def refresh_embedding(
        self,
        connection_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        content_text: str,
        embedding: list[float],
    ) -> MetadataEmbedding:
        """Substitui o embedding de um source (DELETE + INSERT).

        Chamado sempre que o usuário edita descrição/sinônimo/regra pela API, para a
        busca semântica refletir o estado atual dos metadados.
        """
        await self.session.execute(
            delete(MetadataEmbedding).where(
                MetadataEmbedding.source_type == source_type,
                MetadataEmbedding.source_id == source_id,
            )
        )
        return await self.add_embedding(connection_id, source_type, source_id, content_text, embedding)

    async def add_synthetic_example(
        self,
        connection_id: uuid.UUID | None,
        question_nl: str,
        query_sql: str,
        tables_used: list[str],
        difficulty: str | None,
        embedding: list[float],
    ) -> SyntheticExample:
        new_example = SyntheticExample(
            connection_id=connection_id,
            question_nl=question_nl,
            query_sql=query_sql,
            tables_used=tables_used,
            difficulty=difficulty,
            embedding=embedding,
        )
        self.session.add(new_example)
        await self.session.flush()
        return new_example

    # -------------------------------------------------------------- lookups (id)

    async def get_table(self, table_id: uuid.UUID) -> Table | None:
        result = await self.session.execute(
            select(Table).where(Table.id == table_id).options(selectinload(Table.columns))
        )
        return result.scalar_one_or_none()

    async def get_column(self, column_id: uuid.UUID) -> Column | None:
        return await self.session.get(Column, column_id)

    async def get_synonym(self, synonym_id: uuid.UUID) -> Synonym | None:
        return await self.session.get(Synonym, synonym_id)

    async def get_business_rule(self, rule_id: uuid.UUID) -> BusinessRule | None:
        return await self.session.get(BusinessRule, rule_id)

    async def get_enum_value(self, enum_id: uuid.UUID) -> EnumValue | None:
        return await self.session.get(EnumValue, enum_id)

    async def get_table_name_by_id(self, table_id: uuid.UUID) -> str | None:
        result = await self.session.execute(select(Table.table_name).where(Table.id == table_id))
        return result.scalar_one_or_none()

    async def get_table_name_by_column_id(self, column_id: uuid.UUID) -> str | None:
        result = await self.session.execute(
            select(Table.table_name).join(Column, Column.table_id == Table.id).where(Column.id == column_id)
        )
        return result.scalar_one_or_none()

    async def get_table_by_name(
        self, table_name: str, connection_id: _ConnId = None
    ) -> Table | None:
        stmt = (
            select(Table).where(Table.table_name == table_name).options(selectinload(Table.columns))
        )
        if connection_id is not None:
            stmt = stmt.where(Table.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_tables(self, connection_id: _ConnId = None) -> list[Table]:
        stmt = select(Table)
        if connection_id is not None:
            stmt = stmt.where(Table.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_tables_detailed(self, connection_id: uuid.UUID) -> list[Table]:
        result = await self.session.execute(
            select(Table)
            .where(Table.connection_id == connection_id)
            .options(selectinload(Table.columns))
            .order_by(Table.table_name)
        )
        return list(result.scalars().all())

    # ---------------------------------------------------------- deletes (by id)

    async def delete_relationships_for_connection(self, connection_id: uuid.UUID) -> None:
        """Limpa relationships antes de uma re-introspecção (recriadas do zero)."""
        await self.session.execute(
            delete(Relationship).where(Relationship.connection_id == connection_id)
        )

    async def delete_synonym(self, synonym_id: uuid.UUID) -> bool:
        result = await self.session.execute(delete(Synonym).where(Synonym.id == synonym_id))
        return result.rowcount > 0

    async def delete_business_rule(self, rule_id: uuid.UUID) -> bool:
        rule = await self.session.get(BusinessRule, rule_id)
        if rule is None:
            return False
        await self.session.execute(
            delete(MetadataEmbedding).where(
                MetadataEmbedding.source_type == "rule", MetadataEmbedding.source_id == rule_id
            )
        )
        await self.session.delete(rule)
        return True

    async def delete_enum_value(self, enum_id: uuid.UUID) -> bool:
        result = await self.session.execute(delete(EnumValue).where(EnumValue.id == enum_id))
        return result.rowcount > 0

    # ----------------------------------------------------- schema-linking reads

    async def search_synonyms(self, term: str, connection_id: _ConnId = None) -> list[MatchedKeyword]:
        """Busca `term` em synonyms (case-insensitive), resolvendo entity_id para
        nome de tabela/coluna. Duas queries (uma por entity_type) para evitar N+1."""
        pattern = f"%{term}%"
        matches: list[MatchedKeyword] = []

        table_stmt = (
            select(Synonym.synonym, Table.table_name)
            .join(Table, Synonym.entity_id == Table.id)
            .where(Synonym.entity_type == "table", Synonym.synonym.ilike(pattern))
        )
        column_stmt = (
            select(Synonym.synonym, Table.table_name, Column.column_name)
            .join(Column, Synonym.entity_id == Column.id)
            .join(Table, Column.table_id == Table.id)
            .where(Synonym.entity_type == "column", Synonym.synonym.ilike(pattern))
        )
        if connection_id is not None:
            table_stmt = table_stmt.where(Synonym.connection_id == connection_id)
            column_stmt = column_stmt.where(Synonym.connection_id == connection_id)

        for synonym, table_name in await self.session.execute(table_stmt):
            matches.append(
                MatchedKeyword(
                    keyword=term, match_type="synonym", table_name=table_name, matched_value=synonym
                )
            )
        for synonym, table_name, column_name in await self.session.execute(column_stmt):
            matches.append(
                MatchedKeyword(
                    keyword=term,
                    match_type="synonym",
                    table_name=table_name,
                    column_name=column_name,
                    matched_value=synonym,
                )
            )
        return matches

    async def search_enum_values(
        self, term: str, connection_id: _ConnId = None
    ) -> list[MatchedKeyword]:
        """Busca `term` em display_label/stored_value de enum_values (case-insensitive)."""
        pattern = f"%{term}%"
        stmt = (
            select(EnumValue.stored_value, Table.table_name, Column.column_name)
            .join(Column, EnumValue.column_id == Column.id)
            .join(Table, Column.table_id == Table.id)
            .where(or_(EnumValue.display_label.ilike(pattern), EnumValue.stored_value.ilike(pattern)))
        )
        if connection_id is not None:
            stmt = stmt.where(EnumValue.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return [
            MatchedKeyword(
                keyword=term,
                match_type="enum_value",
                table_name=table_name,
                column_name=column_name,
                matched_value=stored_value,
            )
            for stored_value, table_name, column_name in result
        ]

    async def list_relationships_for_tables(
        self, table_names: list[str], connection_id: _ConnId = None
    ) -> list[RelationshipContext]:
        """FKs cujas duas pontas estão no conjunto de tabelas selecionado."""
        source_table = aliased(Table)
        target_table = aliased(Table)
        stmt = (
            select(
                source_table.table_name,
                Relationship.source_column,
                target_table.table_name,
                Relationship.target_column,
            )
            .join(source_table, Relationship.source_table_id == source_table.id)
            .join(target_table, Relationship.target_table_id == target_table.id)
            .where(source_table.table_name.in_(table_names), target_table.table_name.in_(table_names))
        )
        if connection_id is not None:
            stmt = stmt.where(Relationship.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return [
            RelationshipContext(
                source_table=source_table_name,
                source_column=source_column,
                target_table=target_table_name,
                target_column=target_column,
            )
            for source_table_name, source_column, target_table_name, target_column in result
        ]

    async def list_business_rules_for_tables(
        self, table_names: list[str], connection_id: _ConnId = None
    ) -> list[BusinessRuleContext]:
        """Regras das tabelas selecionadas + regras globais (table_id IS NULL)."""
        stmt = (
            select(BusinessRule.rule_text, BusinessRule.rule_type, Table.table_name)
            .outerjoin(Table, BusinessRule.table_id == Table.id)
            .where(or_(Table.table_name.in_(table_names), BusinessRule.table_id.is_(None)))
        )
        if connection_id is not None:
            stmt = stmt.where(BusinessRule.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return [
            BusinessRuleContext(table_name=table_name, rule_text=rule_text, rule_type=rule_type)
            for rule_text, rule_type, table_name in result
        ]

    async def list_business_rules(self, connection_id: uuid.UUID) -> list[BusinessRule]:
        result = await self.session.execute(
            select(BusinessRule).where(BusinessRule.connection_id == connection_id)
        )
        return list(result.scalars().all())

    async def list_enum_values_for_tables(
        self, table_names: list[str], connection_id: _ConnId = None
    ) -> list[EnumValueContext]:
        stmt = (
            select(
                Table.table_name,
                Column.column_name,
                EnumValue.stored_value,
                EnumValue.display_label,
                EnumValue.description,
            )
            .join(Column, EnumValue.column_id == Column.id)
            .join(Table, Column.table_id == Table.id)
            .where(Table.table_name.in_(table_names))
        )
        if connection_id is not None:
            stmt = stmt.where(EnumValue.connection_id == connection_id)
        result = await self.session.execute(stmt)
        return [
            EnumValueContext(
                table_name=table_name,
                column_name=column_name,
                stored_value=stored_value,
                display_label=display_label,
                description=description,
            )
            for table_name, column_name, stored_value, display_label, description in result
        ]

    async def list_synonyms_for_entities(
        self, entity_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[Synonym]]:
        if not entity_ids:
            return {}
        result = await self.session.execute(
            select(Synonym).where(Synonym.entity_id.in_(entity_ids))
        )
        grouped: dict[uuid.UUID, list[Synonym]] = {}
        for synonym in result.scalars():
            grouped.setdefault(synonym.entity_id, []).append(synonym)
        return grouped

    async def list_enum_values_for_columns(
        self, column_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[EnumValue]]:
        if not column_ids:
            return {}
        result = await self.session.execute(
            select(EnumValue).where(EnumValue.column_id.in_(column_ids))
        )
        grouped: dict[uuid.UUID, list[EnumValue]] = {}
        for enum_value in result.scalars():
            grouped.setdefault(enum_value.column_id, []).append(enum_value)
        return grouped
