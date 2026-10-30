/** Link para a fonte original - abre fora do terminal. */
export function LinkFonte({ href, children }: { href?: string | null; children: React.ReactNode }) {
  if (!href || !/^https?:\/\//.test(href)) return <>{children}</>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="hover:text-ambar hover:underline">
      {children}
    </a>
  );
}
