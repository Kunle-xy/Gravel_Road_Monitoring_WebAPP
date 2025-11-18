// app/[slug]/page.tsx
import React from "react";
import RutForm from "@/app/components/DistressForms/rut";
import CorrugationForm from "@/app/components/DistressForms/corrugation";

export const metadata = {
  title: "Distress Page",
  description: "Details about the selected distress type.",
};

const DistressForms: Record<string, React.ReactNode> = {
  rut: <RutForm />,
  corrugation: <CorrugationForm />,
};

export default async function DistressPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  return (
    <div className="bg-white outline absolute right-3 top-2 rounded-sm p-3 w-[22rem] sm:w-[24rem] md:w-[26rem] max-w-[92vw] z-20">
      <h1 className="text-xs font-semibold mb-2 text-center text-red-800">
        <strong>{slug}</strong> automatic detection
      </h1>
      <div className="w-full">{DistressForms[slug]}</div>
    </div>
  );
}
