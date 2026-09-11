import type { DbType } from "./types";

interface DbTypeInfo {
  label: string;
  icon: string;
  /** Cor da marca do banco (spec Inquiro §Connection Card). */
  brandColor: string;
  defaultPort: number;
  /** Só PostgreSQL/SQL Server usam `schema_name`; os demais usam só o database. */
  usesSchema: boolean;
  supported: boolean;
}

export const DB_TYPES: Record<DbType, DbTypeInfo> = {
  postgresql: { label: "PostgreSQL", icon: "🐘", brandColor: "#336791", defaultPort: 5432, usesSchema: true, supported: true },
  mysql: { label: "MySQL", icon: "🐬", brandColor: "#4479A1", defaultPort: 3306, usesSchema: false, supported: true },
  sqlserver: { label: "SQL Server", icon: "🪟", brandColor: "#CC2927", defaultPort: 1433, usesSchema: true, supported: true },
  oracle: { label: "Oracle", icon: "🔴", brandColor: "#F80000", defaultPort: 1521, usesSchema: false, supported: false },
  sqlite: { label: "SQLite", icon: "📄", brandColor: "#003B57", defaultPort: 0, usesSchema: false, supported: false },
};

export const SUPPORTED_DB_TYPES = (Object.keys(DB_TYPES) as DbType[]).filter((t) => DB_TYPES[t].supported);

export function dbTypeInfo(dbType: string): DbTypeInfo {
  return DB_TYPES[dbType as DbType] ?? DB_TYPES.postgresql;
}
