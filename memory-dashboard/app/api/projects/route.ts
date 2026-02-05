import { NextResponse } from "next/server";
import { getProjects } from "@/lib/queries";

export async function GET() {
  try {
    const projects = getProjects();
    return NextResponse.json(projects);
  } catch (error) {
    return NextResponse.json(
      { error: String(error) },
      { status: 500 }
    );
  }
}
