import { NextRequest, NextResponse } from "next/server";
import { getEvents } from "@/lib/queries";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);

    const result = getEvents({
      projectHash: searchParams.get("projectHash") || undefined,
      category: searchParams.get("category") || undefined,
      search: searchParams.get("search") || undefined,
      limit: parseInt(searchParams.get("limit") || "50"),
      offset: parseInt(searchParams.get("offset") || "0"),
    });

    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: String(error) },
      { status: 500 }
    );
  }
}
