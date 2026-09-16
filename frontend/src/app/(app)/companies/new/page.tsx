"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Banner, Card } from "@/components/ui";
import { CompanyForm } from "@/components/CompanyForm";

function NewCompany() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [warnings, setWarnings] = useState<string[]>([]);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link href="/companies" className="text-sm text-muted hover:text-accent-hi">
          ← Companies
        </Link>
        <h1 className="mt-2 text-xl font-semibold tracking-tight">Add a company</h1>
        <p className="mt-1 text-sm text-muted">
          Any company you advise, including one that is not registered yet. Capital and
          shareholders are recorded next.
        </p>
      </div>

      {warnings.length > 0 && (
        <Banner tone="warn" title="Check this is not a duplicate">
          <ul className="list-disc pl-4">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </Banner>
      )}

      <Card className="p-6">
        <CompanyForm
          onCancel={() => router.push("/companies")}
          onCreated={(c) => {
            if (c.warnings.length) { setWarnings(c.warnings); return; }
            // Straight into the wizard, which resumes at the first step this
            // company still needs - capital, for a company just created.
            router.push(next === "companies"
              ? "/companies" : `/assess?company=${c.company_id}`);
          }} />
      </Card>
    </div>
  );
}

export default function NewCompanyPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}>
      <NewCompany />
    </Suspense>
  );
}
