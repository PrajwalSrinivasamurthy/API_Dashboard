import { DashboardClient } from "@/app/dashboard/DashboardClient";
import { dashboardEnvReady } from "@/lib/server-backend";

export const dynamic = "force-dynamic";

export default function DashboardPage() {
  const configured = dashboardEnvReady();
  return <DashboardClient serverConfigured={configured} />;
}
