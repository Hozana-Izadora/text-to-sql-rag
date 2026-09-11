import { ChatView } from "@/components/chat/ChatView";

export default async function ConnectionChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ChatView connectionId={id} />;
}
