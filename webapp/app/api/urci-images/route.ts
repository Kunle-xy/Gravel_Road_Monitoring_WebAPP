import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

// List PNG/JPG files in `webapp/public/urci/`. Rebuild-free — drop a file
// into the folder and it shows up on the next Final URCI form load.
export const dynamic = "force-dynamic";

export async function GET() {
  const dir = path.join(process.cwd(), "public", "urci");
  try {
    const files = fs
      .readdirSync(dir)
      .filter((f) => /\.(png|jpe?g)$/i.test(f))
      .sort();
    return NextResponse.json({ files });
  } catch {
    return NextResponse.json({ files: [] });
  }
}
