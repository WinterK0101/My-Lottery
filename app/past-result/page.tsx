'use client';

import { FormEvent, useMemo, useState } from 'react';
import Navigation from '../components/navigation';

type GameType = '4D' | 'TOTO';

type FourDResult = {
  first_prize?: string | string[];
  second_prize?: string | string[];
  third_prize?: string | string[];
  starter?: string[];
  consolation?: string[];
};

type TotoResult = {
  winning_numbers?: number[];
  additional_number?: number;
};

type PastResultResponse = {
  status?: string;
  source?: string;
  game_type?: GameType;
  draw_date?: string;
  draw_id?: string;
  draw_number?: string;
  results?: FourDResult | TotoResult;
  additional_number?: number;
  message?: string;
};

const formatDateInput = (date: Date): string => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const formatDrawDate = (value: string | undefined): string => {
  if (!value) return 'Unknown date';

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleDateString('en-SG', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const getApiBaseUrl = (): string => {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) return configuredBaseUrl.replace(/\/$/, '');

  if (typeof window !== 'undefined') {
    const { hostname, origin } = window.location;
    const isPrivate172 = /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname);
    const isLocalHost =
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname.startsWith('192.168.') ||
      hostname.startsWith('10.') ||
      isPrivate172 ||
      hostname.endsWith('.local');

    if (isLocalHost) return `http://${hostname}:8000`;
    return origin;
  }

  return 'http://localhost:8000';
};

const parseJsonResponse = async (response: Response): Promise<unknown> => {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    const bodyText = await response.text();
    throw new Error(
      `Expected JSON from results API but received '${contentType || 'unknown'}'. ${bodyText.slice(0, 120)}`
    );
  }

  return response.json();
};

const toStringArray = (value: string | string[] | undefined): string[] => {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  return [value];
};

export default function PastResultPage() {
  const [gameType, setGameType] = useState<GameType>('TOTO');
  const [drawDate, setDrawDate] = useState<string>(formatDateInput(new Date()));
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PastResultResponse | null>(null);

  const hasResult = useMemo(() => Boolean(result && !error), [result, error]);

  const fetchPastResult = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${getApiBaseUrl()}/api/results/past/${encodeURIComponent(gameType)}?draw_date=${encodeURIComponent(drawDate)}`,
        {
          cache: 'no-store',
          headers: {
            'ngrok-skip-browser-warning': '1',
          },
        }
      );

      const payload = await parseJsonResponse(response);

      if (!response.ok) {
        const detail =
          payload && typeof payload === 'object' && 'detail' in payload
            ? String(payload.detail)
            : `Request failed with status ${response.status}`;
        throw new Error(detail);
      }

      setResult(payload as PastResultResponse);
    } catch (fetchError) {
      setResult(null);
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to load past result.');
    } finally {
      setLoading(false);
    }
  };

  const fetchLatestResult = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        `${getApiBaseUrl()}/api/results/latest/${encodeURIComponent(gameType)}`,
        {
          cache: 'no-store',
          headers: {
            'ngrok-skip-browser-warning': '1',
          },
        }
      );

      const payload = await parseJsonResponse(response);

      if (!response.ok) {
        const detail =
          payload && typeof payload === 'object' && 'detail' in payload
            ? String(payload.detail)
            : `Request failed with status ${response.status}`;
        throw new Error(detail);
      }

      const latestResult = payload as PastResultResponse;
      setResult(latestResult);
      if (latestResult.draw_date) {
        setDrawDate(latestResult.draw_date);
      }
    } catch (fetchError) {
      setResult(null);
      setError(fetchError instanceof Error ? fetchError.message : 'Unable to load latest result.');
    } finally {
      setLoading(false);
    }
  };

  const renderTotoResult = (results: TotoResult | undefined) => {
    const winningNumbers = Array.isArray(results?.winning_numbers) ? results?.winning_numbers : [];
    const additionalNumber =
      typeof results?.additional_number === 'number'
        ? results.additional_number
        : typeof result?.additional_number === 'number'
          ? result.additional_number
          : null;

    return (
      <div className="space-y-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Winning Numbers</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {winningNumbers.length > 0 ? (
              winningNumbers.map((num, idx) => (
                <span
                  key={`toto-winning-${idx}`}
                  className="rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold font-mono text-blue-900"
                >
                  {num}
                </span>
              ))
            ) : (
              <p className="text-sm text-gray-700">No winning numbers available.</p>
            )}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Additional Number</p>
          <p className="mt-1 text-lg font-bold text-gray-900">
            {additionalNumber !== null ? additionalNumber : 'Not available'}
          </p>
        </div>
      </div>
    );
  };

  const renderFourDResult = (results: FourDResult | undefined) => {
    const firstPrize = toStringArray(results?.first_prize);
    const secondPrize = toStringArray(results?.second_prize);
    const thirdPrize = toStringArray(results?.third_prize);
    const starter = Array.isArray(results?.starter) ? results.starter : [];
    const consolation = Array.isArray(results?.consolation) ? results.consolation : [];

    return (
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border border-blue-300 bg-blue-100 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-900">1st Prize</p>
            <p className="mt-2 text-xl font-bold text-gray-900">{firstPrize.join(', ') || 'N/A'}</p>
          </div>
          <div className="rounded-lg border border-blue-300 bg-blue-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-900">2nd Prize</p>
            <p className="mt-2 text-xl font-bold text-gray-900">{secondPrize.join(', ') || 'N/A'}</p>
          </div>
          <div className="rounded-lg border border-blue-300 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-800">3rd Prize</p>
            <p className="mt-2 text-xl font-bold text-gray-900">{thirdPrize.join(', ') || 'N/A'}</p>
          </div>
        </div>

        <div className="mt-6 border-t-2 border-gray-300 pt-6">
          <p className="text-xs font-bold uppercase tracking-widest text-gray-600 mb-4">Other Prize Tiers</p>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-gray-300 bg-gray-100 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-700">Starter Prize</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {starter.length > 0 ? (
                  starter.map((value, idx) => (
                    <span
                      key={`starter-${idx}`}
                      className="rounded-full bg-gray-200 px-3 py-1 text-sm font-semibold font-mono text-gray-800 ring-1 ring-gray-400"
                    >
                      {value}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-gray-600">No starter numbers available.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-300 bg-gray-100 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-700">Consolation Prize</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {consolation.length > 0 ? (
                  consolation.map((value, idx) => (
                    <span
                      key={`consolation-${idx}`}
                      className="rounded-full bg-gray-200 px-3 py-1 text-sm font-semibold font-mono text-gray-800 ring-1 ring-gray-400"
                    >
                      {value}
                    </span>
                  ))
                ) : (
                  <p className="text-sm text-gray-600">No consolation numbers available.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <>
      <Navigation />

      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="mx-auto max-w-4xl space-y-6">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Past Result</h1>
            <p className="text-gray-700">Check historical draw outcomes for 4D and TOTO.</p>
          </div>

          <form
            className="bg-white rounded-lg shadow-lg p-6 border border-blue-100"
            onSubmit={(event) => {
              void fetchPastResult(event);
            }}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-medium text-gray-900">
                Game Type
                <select
                  className="mb-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-blue-200 focus:ring"
                  value={gameType}
                  onChange={(event) => setGameType(event.target.value as GameType)}
                >
                  <option value="4D">4D</option>
                  <option value="TOTO">TOTO</option>
                </select>
              </label>

              <label className="text-sm font-medium text-gray-900">
                Draw Date
                <input
                  type="date"
                  className="mb-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-blue-200 focus:ring"
                  value={drawDate}
                  onChange={(event) => setDrawDate(event.target.value)}
                  required
                />
              </label>
            </div>

            <div className="mt-8 flex flex-wrap gap-3">
              <button
                type="submit"
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={loading}
              >
                {loading ? 'Loading...' : 'Find Past Result'}
              </button>

              <button
                type="button"
                className="rounded-lg border border-blue-300 bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={() => {
                  void fetchLatestResult();
                }}
                disabled={loading}
              >
                Load Latest {gameType}
              </button>
            </div>
          </form>

          {error && (
            <div className="bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border-2 border-red-300 p-5">
              <p className="text-sm font-semibold text-rose-700">Unable to load results</p>
              <p className="mt-1 text-sm text-rose-600">{error}</p>
            </div>
          )}

          {!error && !loading && !hasResult && (
            <div className="bg-white rounded-lg shadow-lg p-8 border border-blue-100">
              <p className="text-sm text-gray-800">Select a game and draw date to view past results.</p>
            </div>
          )}

          {!error && hasResult && result && (
            <div className="bg-white rounded-lg shadow-lg p-6 md:p-8 border border-blue-100 space-y-6">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-blue-100 px-3 py-1 text-sm font-semibold text-blue-900 ring-1 ring-blue-300">
                  {result.game_type || gameType}
                </span>
                <span className="rounded-full  px-3 py-1 text-sm font-semibold text-blue-800 ring-1 ring-blue-300">
                  {formatDrawDate(result.draw_date)}
                </span>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <p className="text-sm text-gray-800">
                  <span className="font-semibold text-gray-900">Draw Ref:</span>{' '}
                  {result.draw_id || result.draw_number || 'Not available'}
                </p>
              </div>

              {(result.game_type || gameType) === 'TOTO'
                ? renderTotoResult(result.results as TotoResult | undefined)
                : renderFourDResult(result.results as FourDResult | undefined)}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
