export function PageHeader({ eyebrow, title, children }: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="page-header">
      <p className="eyebrow">{eyebrow}</p>
      <div className="page-header-copy">
        <h1 className="page-title">{title}</h1>
        {children}
      </div>
    </header>
  );
}
