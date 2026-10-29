import { getToken } from "next-auth/jwt";
import { NextResponse, type NextRequest } from "next/server";

/** Todo o terminal exige login. Sem o login configurado, nada abre
 * (falha fechada): o usuário cai em /login, que explica o que falta.
 * PREGAO_DIAG_SEM_LOGIN só vale FORA da Vercel (VERCEL não definido) -
 * usado pelo runner de validação, nunca em produção. */
export async function middleware(req: NextRequest) {
  const diag = process.env.PREGAO_DIAG_SEM_LOGIN === "1" && !process.env.VERCEL;
  if (diag) return NextResponse.next();
  const segredo = process.env.NEXTAUTH_SECRET;
  const token = segredo ? await getToken({ req, secret: segredo }) : null;
  if (token) return NextResponse.next();
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!login|api/auth|_next/static|_next/image|favicon.ico).*)"],
};
