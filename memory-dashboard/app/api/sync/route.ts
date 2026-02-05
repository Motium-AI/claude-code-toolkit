import { NextResponse } from "next/server";
import { syncMemoryData, updateLastSyncTime, getLastSyncTime } from "@/lib/sync";

export async function POST() {
  try {
    const result = syncMemoryData();
    updateLastSyncTime();

    return NextResponse.json({
      success: true,
      ...result,
      lastSync: getLastSyncTime(),
    });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}

export async function GET() {
  return NextResponse.json({
    lastSync: getLastSyncTime(),
  });
}
