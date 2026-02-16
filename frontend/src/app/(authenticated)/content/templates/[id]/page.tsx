import TemplateDetail from "./TemplateDetail";

export async function generateStaticParams() {
  return [{ id: "_" }];
}

export default function TemplateDetailPage() {
  return <TemplateDetail />;
}
