"use client";

import { useState } from "react";

import Navigation from "../components/navigation";

// ─── Types ────────────────────────────────────────────────────────────────────

interface FourDPrediction {
  number: string;
  confidence: number;
  reasoning: string;
}

interface TotoPrediction {
  numbers: number[];
  primary: number[];
  supplementary: number[];
  confidence: number;
  reasoning: string;
}

interface ModelPrediction {
  model_name: string;
  model_key: string;
  description: string;
  four_d: FourDPrediction;
  toto: TotoPrediction;
  methodology: string;
  assumptions: string;
  validation: string;
  confidence_note: string;
}

interface PredictionResponse {
  disclaimer: string;
  models: ModelPrediction[];
  data_points_used: number;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const MODEL_META: Record<
  string,
  { icon: string; border: string; accent: string; badge: string; tagline: string; title: string }
> = {
  frequency: {
    icon: "🔥",
    border: "border-orange-200",
    accent: "text-orange-600",
    badge: "bg-orange-50 text-orange-700 border border-orange-200",
    tagline: "Hot numbers keep appearing",
    title: "Frequency Analysis",
  },
  markov: {
    icon: "⛓️",
    border: "border-indigo-200",
    accent: "text-indigo-600",
    badge: "bg-indigo-50 text-indigo-700 border border-indigo-200",
    tagline: "Next draw follows the last",
    title: "Markov Chain",
  },
  gap: {
    icon: "⏳",
    border: "border-teal-200",
    accent: "text-teal-600",
    badge: "bg-teal-50 text-teal-700 border border-teal-200",
    tagline: "Overdue numbers are coming",
    title: "Gap Analysis",
  },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function safeParseJson(response: Response): Promise<any> {
  const ct = response.headers.get("content-type") || "";
  if (ct.includes("application/json")) return response.json();
  const text = await response.text();
  return { detail: text?.slice(0, 500) || "Unexpected non-JSON response from server." };
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const bar =
    pct >= 40 ? "bg-green-500" : pct >= 25 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden border border-gray-200">
        <div
          className={`h-full rounded-full transition-all duration-700 ${bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-gray-500 w-8 text-right">{pct}%</span>
    </div>
  );
}

function FourDBall({ digit }: { digit: string }) {
  return (
    <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-amber-100 border-2 border-amber-300 text-amber-700 font-mono font-bold text-lg shadow-sm">
      {digit}
    </span>
  );
}

function TotoBall({ number, isSupplementary }: { number: number; isSupplementary?: boolean }) {
  return (
    <span
      className={`inline-flex items-center justify-center w-9 h-9 rounded-full font-mono font-semibold text-sm shadow-sm ${
        isSupplementary
          ? "bg-gray-100 border border-gray-300 text-gray-500"
          : "bg-blue-100 border-2 border-blue-300 text-blue-700"
      }`}
    >
      {String(number).padStart(2, "0")}
    </span>
  );
}

function ModelCard({ model }: { model: ModelPrediction }) {
  const meta = MODEL_META[model.model_key] ?? MODEL_META.frequency;

  return (
    <div className={`bg-white rounded-lg shadow-lg overflow-hidden border-t-4 ${meta.border}`}>
      {/* Header */}
      <div className="px-6 pt-5 pb-4 border-b border-gray-100">
        <div className="flex items-start gap-3 mb-3">
          <span className="text-2xl mt-0.5">{meta.icon}</span>
          <div className="min-w-0">
            <h3 className={`font-bold text-base ${meta.accent}`}>{model.model_name}</h3>
            <p className="text-xs text-gray-500 mt-0.5 leading-snug">{model.description}</p>
          </div>
        </div>
      </div>

      <div className="p-5 space-y-5">
        {/* 4D */}
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            4D Prediction
          </p>
          <div className="flex items-center gap-2 mb-3">
            {model.four_d.number.split("").map((d, i) => (
              <FourDBall key={i} digit={d} />
            ))}
          </div>
          <ConfidenceMeter value={model.four_d.confidence} />
          <p className="mt-2 text-xs text-gray-500 leading-relaxed">
            {model.four_d.reasoning}
          </p>
        </div>

        {/* Divider */}
        <hr className="border-gray-100" />

        {/* TOTO */}
        <div>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            TOTO System 12
          </p>
          <div className="mb-3">
            <p className="text-xs text-gray-400 mb-1.5">Primary (6)</p>
            <div className="flex flex-wrap gap-1.5">
              {model.toto.primary.map((n) => (
                <TotoBall key={`p-${n}`} number={n} />
              ))}
            </div>
          </div>
          <div className="mb-3">
            <p className="text-xs text-gray-400 mb-1.5">Supplementary (6)</p>
            <div className="flex flex-wrap gap-1.5">
              {model.toto.supplementary.map((n) => (
                <TotoBall key={`s-${n}`} number={n} isSupplementary />
              ))}
            </div>
          </div>
          <ConfidenceMeter value={model.toto.confidence} />
          <p className="mt-2 text-xs text-gray-500 leading-relaxed">
            {model.toto.reasoning}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function PredictionPage() {
  const [predictions, setPredictions] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agreed, setAgreed] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const predRes = await fetch("/api/predictions/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ limit: 50 }),
      });
      const payload = await safeParseJson(predRes);
      if (!predRes.ok) throw new Error(payload?.detail ?? "Prediction failed.");
      setPredictions(payload as PredictionResponse);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navigation />
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="max-w-5xl mx-auto space-y-6">

          {/* Page header card */}
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Predictive Analysis</h1>
            <p className="text-gray-600">
              Three independent statistical models analyse historical draw data to generate number
              suggestions. For educational purposes only.
            </p>
          </div>

          {/* Disclaimer / consent gate */}
          {!agreed && (
            <div className="bg-white rounded-lg shadow-lg p-6 border-l-4 border-amber-400">
              <div className="flex gap-4">
                <span className="text-3xl">⚠️</span>
                <div>
                  <p className="font-semibold text-gray-800 mb-1 text-lg">Educational Use Only</p>
                  <p className="text-sm text-gray-600 leading-relaxed mb-4">
                    All predictions are generated purely for educational and entertainment purposes.
                    They are <strong>NOT</strong> financial or gambling advice. Lottery draws are
                    random — no algorithm can reliably predict outcomes. Please gamble responsibly.
                  </p>
                  <button
                    onClick={() => setAgreed(true)}
                    className="bg-gradient-to-r from-blue-600 to-blue-700 text-white p-2 rounded-lg shadow-md hover:shadow-lg transition font-semibold text-sm"
                  >
                    I understand — continue
                  </button>
                </div>
              </div>
            </div>
          )}

          {agreed && (
            <>
              {/* Model overview */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {Object.entries(MODEL_META).map(([key, meta]) => (
                  <div key={key} className="bg-white rounded-lg shadow p-5 border-t-4 border-blue-300">
                    <span className="text-2xl">{meta.icon}</span>
                    <p className={`font-bold text-sm mt-2 ${meta.accent}`}>{meta.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{meta.tagline}</p>
                  </div>
                ))}
              </div>

              {/* Generate action bar */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <div className="flex flex-wrap items-center gap-4">
                  <button
                    onClick={generate}
                    disabled={loading}
                    className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-3 rounded-lg shadow-md hover:shadow-lg transition font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                  >
                    {loading ? (
                      <>
                        <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                          <circle
                            cx="12" cy="12" r="10"
                            stroke="currentColor" strokeWidth="2"
                            strokeDasharray="32" strokeLinecap="round"
                          />
                        </svg>
                        Analysing draws…
                      </>
                    ) : (
                      "✨ Generate Predictions"
                    )}
                  </button>
                  {predictions && (
                    <p className="text-sm text-gray-500">
                      Based on{" "}
                      <span className="font-semibold text-gray-700">
                        {predictions.data_points_used}
                      </span>{" "}
                      historical draws
                    </p>
                  )}
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="bg-gradient-to-r from-red-50 to-orange-50 border-2 border-red-300 rounded-lg p-4">
                  <p className="text-red-700 font-semibold text-sm">{error}</p>
                </div>
              )}

              {/* Results */}
              {predictions && (
                <div className="grid md:grid-cols-3 gap-5">
                  {predictions.models.map((m) => (
                    <ModelCard key={m.model_key} model={m} />
                  ))}
                </div>
              )}

              {/* Persistent disclaimer */}
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <p className="text-sm text-gray-600 text-center">
                  💡 Predictions are statistical approximations for educational use only. They do
                  not constitute gambling advice. Lottery draws are random events.
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
