import { MetadataEditor } from "@/components/metadata/MetadataEditor";

export default async function MetadataPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MetadataEditor connectionId={id} />;
}
