'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import Navigation from '../components/navigation';

type GameTypeFilter = 'ALL' | '4D' | 'TOTO';
type StatusFilter = 'ALL' | 'pending' | 'won' | 'lost';
type SortBy = 'draw_date_desc' | 'prize_amount_desc';

type CombinationAnalysis = {
  combination_index: number;
  numbers: number[];
  matched_numbers: number[];
  matched_count: number;
  has_additional: boolean;
  tier: string;
  is_winning: boolean;
};

type TicketRecord = {
  id: string;
  game_type: string;
  ticket_type: string;
  draw_date: string;
  draw_id?: string | null;
  ticket_serial_number?: string | null;
  selected_numbers: number[];
  combinations_count?: number | null;
  ocr_confidence?: number | null;
  metadata?: Record<string, unknown> | null;
  status: string;
  prize_tier?: string | null;
  winning_amount?: number | string | null;
  evaluation_result?: Record<string, unknown> | null;
  expanded_combinations?: number[][];
  combination_analysis?: CombinationAnalysis[];
  winning_combination_indexes?: number[];
  winning_combinations?: CombinationAnalysis[];
  draw_result?: Record<string, unknown>;
  results_lookup_error?: string;
  evaluation_error?: string;
  created_at?: string;
  image_url?: string | null;
};

type HistorySummary = {
  total_tickets: number;
  total_spent: number;
  total_winnings: number;
  active_tickets: number;
  status_counts: Record<string, number>;
  game_type_counts: Record<string, number>;
  match_counts: Record<string, number>;
};

type HistoryResponse = {
  user_id: string;
  summary: HistorySummary;
  tickets: TicketRecord[];
};

const currencyFormatter = new Intl.NumberFormat('en-SG', {
  style: 'currency',
  currency: 'SGD',
  maximumFractionDigits: 2,
});

const getUserId = (): string => {
  return process.env.NEXT_PUBLIC_USER_ID || 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d';
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

const toNumber = (value: unknown): number => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  if (typeof value === 'string') {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
};

const formatMoney = (value: unknown): string => currencyFormatter.format(toNumber(value));

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

const statusBadgeClass = (status: string): string => {
  const normalized = status.toLowerCase();
  if (normalized === 'won') return 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-300';
  if (normalized === 'lost') return 'bg-rose-100 text-gray-900 ring-1 ring-rose-300';
  return 'text-gray-900 ring-1 ring-blue-300';
};

const gameTypeClass = (gameType: string): string => {
  if (gameType === 'TOTO') return 'bg-sky-100 text-gray-900 ring-1 ring-sky-300';
  return 'bg-indigo-100 text-gray-900 ring-1 ring-indigo-300';
};

const sortTickets = (tickets: TicketRecord[], sortBy: SortBy): TicketRecord[] => {
  const cloned = [...tickets];

  if (sortBy === 'prize_amount_desc') {
    return cloned.sort((a, b) => toNumber(b.winning_amount) - toNumber(a.winning_amount));
  }

  return cloned.sort((a, b) => {
    const dateA = new Date(a.draw_date || '').getTime();
    const dateB = new Date(b.draw_date || '').getTime();
    return (Number.isNaN(dateB) ? 0 : dateB) - (Number.isNaN(dateA) ? 0 : dateA);
  });
};

const parseJsonResponse = async (response: Response): Promise<unknown> => {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    const bodyText = await response.text();
    throw new Error(
      `Expected JSON from history API but received '${contentType || 'unknown'}'. ${bodyText.slice(0, 120)}`
    );
  }

  return response.json();
};

function TotoDetailPanel({ ticket }: { ticket: TicketRecord }) {
  const drawResult = ticket.draw_result || null;
  const winningNumbersRaw = drawResult ? drawResult['winning_numbers'] : undefined;
  const additionalRaw = drawResult ? drawResult['additional_number'] : undefined;
  const winningNumbers = Array.isArray(winningNumbersRaw) ? winningNumbersRaw : [];
  const additionalNumber = typeof additionalRaw === 'number' ? additionalRaw : null;

  const isSystemTicket = (ticket.ticket_type || '').toLowerCase().includes('system');
  let detectedTicketGroups: number[][] = [];

  if (!isSystemTicket) {
    const expandedGroups = (ticket.expanded_combinations || []).filter(
      (group): group is number[] =>
        Array.isArray(group) && group.length > 0 && group.every((value) => typeof value === 'number')
    );

    if (expandedGroups.length > 0) {
      detectedTicketGroups = expandedGroups;
    } else if (Array.isArray(ticket.selected_numbers) && ticket.selected_numbers.length > 0) {
      detectedTicketGroups = [ticket.selected_numbers];
    }
  }

  const comboAnalysis =
    ticket.combination_analysis && ticket.combination_analysis.length > 0
      ? ticket.combination_analysis
      : (ticket.expanded_combinations || []).map((numbers, index) => ({
          combination_index: index,
          numbers,
          matched_numbers: [],
          matched_count: 0,
          has_additional: false,
          tier: 'No Prize',
          is_winning: false,
        }));

  const winningIndexSet = new Set(ticket.winning_combination_indexes || []);

  return (
    <div className="w-full p-6 bg-white rounded-lg border-2 border-blue-200">
      <h2 className="font-bold text-gray-900 text-lg mb-4">✓ Ticket Details</h2>
      
      {/* Ticket Image Preview */}
      {ticket.image_url && (
        <div className="relative w-full border-4 border-dashed border-blue-300 rounded-xl overflow-hidden bg-gray-100 shadow-inner mb-4">
          <img 
            src={ticket.image_url} 
            alt="Ticket Image" 
            className="w-full h-auto block"
          />
        </div>
      )}
      
      <div className="space-y-2">
        <p className="text-gray-900">
          <span className="font-semibold text-gray-950">Game:</span> {ticket.game_type}
        </p>
        <p className="text-gray-900">
          <span className="font-semibold text-gray-950">Ticket Type:</span> {ticket.ticket_type || 'N/A'}
        </p>
        <p className="text-gray-900">
          <span className="font-semibold text-gray-950">Purchase Date:</span>{' '}
          {ticket.created_at ? formatDrawDate(ticket.created_at) : 'N/A'}
        </p>
        <p className="text-gray-900">
          <span className="font-semibold text-gray-950">Draw Date:</span> {formatDrawDate(ticket.draw_date)}
        </p>
        {ticket.draw_id && (
          <p className="text-gray-900">
            <span className="font-semibold text-gray-950">Draw ID:</span> {ticket.draw_id}
          </p>
        )}
        {ticket.ticket_serial_number && (
          <p className="text-gray-900">
            <span className="font-semibold text-gray-950">Ticket Serial:</span> {ticket.ticket_serial_number}
          </p>
        )}

        <div className="mt-4 p-3 bg-white rounded border border-green-200">
          <span className="font-semibold text-gray-950 block mb-2">Detected Numbers:</span>
          {detectedTicketGroups.length > 0 ? (
            <div className="space-y-3">
              {detectedTicketGroups.map((group, groupIdx) => (
                <div key={`${ticket.id}-group-${groupIdx}`} className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-extrabold text-blue-950 min-w-[24px]">
                    {String.fromCharCode(65 + groupIdx)}
                  </span>
                  {group.map((num, idx) => (
                    <span
                      key={`${ticket.id}-group-${groupIdx}-num-${idx}`}
                      className="px-3 py-1 bg-blue-100 text-blue-900 rounded-full font-mono font-bold"
                    >
                      {num}
                    </span>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {(ticket.selected_numbers || []).map((num: number, idx: number) => (
                <span key={idx} className="px-3 py-1 bg-blue-100 text-blue-900 rounded-full font-mono font-bold">
                  {num}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Winning Status Section */}
        <div className="mt-4 p-3 bg-white rounded border border-blue-200">
          <span className="font-semibold text-gray-950 block mb-2">Result Status:</span>
          
          <div
            className={`mt-3 rounded-lg border p-4 ${
              ticket.status === 'won'
                ? 'bg-green-50 border-green-300'
                : ticket.status === 'lost'
                ? 'bg-gray-50 border-gray-300'
                : 'bg-blue-50 border-blue-300'
            }`}
          >
            <p className="text-gray-800 font-semibold mb-2">
              {ticket.status === 'won' ? '🎉 Winner!' : ticket.status === 'lost' ? '📊 No Prize' : 'ℹ️ Pending'}
            </p>
            
            {ticket.status === 'won' && (
              <>
                <p className="text-gray-700">
                  <span className="font-semibold">Prize Tier:</span> {ticket.prize_tier || 'N/A'}
                </p>
                <p className="text-gray-700">
                  <span className="font-semibold">Winning Amount:</span> {formatMoney(ticket.winning_amount)}
                </p>
                {ticket.winning_combinations && ticket.winning_combinations.length > 0 && (
                  <p className="text-emerald-700 mt-2 text-sm">
                    {ticket.winning_combinations.length} winning combination(s) found
                  </p>
                )}
              </>
            )}

            {ticket.status === 'lost' && (
              <p className="text-gray-700">
                This ticket did not win any prizes for the draw on {formatDrawDate(ticket.draw_date)}.
              </p>
            )}

            {ticket.status === 'pending' && (
              <p className="text-gray-700">
                Results will be available after the draw on {formatDrawDate(ticket.draw_date)}.
              </p>
            )}
          </div>

          {/* Draw Results (if available) */}
          {drawResult && (winningNumbers.length > 0 || additionalNumber !== null) && (
            <div className="mt-3 p-3 bg-blue-50 rounded border border-blue-200">
              <p className="font-semibold text-gray-950 mb-2">Official Draw Results:</p>
              <p className="text-sm text-gray-800">
                <span className="font-semibold">Winning Numbers:</span>{' '}
                {winningNumbers.length > 0 ? winningNumbers.join(', ') : 'Not available'}
              </p>
              {additionalNumber !== null && (
                <p className="text-sm text-gray-800">
                  <span className="font-semibold">Additional Number:</span> {additionalNumber}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Expanded Combinations Section (Collapsible) */}
        {comboAnalysis.length > 0 && (
          <details className="mt-4 rounded-lg border border-gray-200 bg-white px-4 py-3">
            <summary className="cursor-pointer text-sm font-semibold text-gray-900">
              View All Combinations ({comboAnalysis.length} sets)
            </summary>
            <div className="mt-3 max-h-80 space-y-3 overflow-y-auto pr-1">
              {comboAnalysis.map((combo) => {
                const isWinning = combo.is_winning || winningIndexSet.has(combo.combination_index);
                return (
                  <div
                    key={`${ticket.id}-combo-${combo.combination_index}`}
                    className={`rounded-lg border px-3 py-2 ${
                      isWinning ? 'border-emerald-300 bg-emerald-50' : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-xs font-semibold text-gray-900">Set #{combo.combination_index + 1}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          isWinning ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-200 text-gray-900'
                        }`}
                      >
                        {isWinning ? combo.tier || 'Winning Set' : combo.tier || 'No Prize'}
                      </span>
                    </div>

                    <div className="mt-2 flex flex-wrap gap-2">
                      {combo.numbers.map((number, index) => {
                        const isMatched = combo.matched_numbers.includes(number);
                        return (
                          <span
                            key={`${ticket.id}-combo-${combo.combination_index}-${index}`}
                            className={`rounded-full px-3 py-1 text-xs font-semibold font-mono ${
                              isMatched ? 'bg-emerald-200 text-emerald-800' : 'bg-blue-100 text-blue-900'
                            }`}
                          >
                            {number}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

export default function PurchaseHistoryPage() {
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [gameTypeFilter, setGameTypeFilter] = useState<GameTypeFilter>('ALL');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');
  const [sortBy, setSortBy] = useState<SortBy>('draw_date_desc');
  const [expandedTicketId, setExpandedTicketId] = useState<string | null>(null);

  const userId = getUserId();

  useEffect(() => {
    const loadHistory = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(
          `${getApiBaseUrl()}/api/tickets/${encodeURIComponent(userId)}`,
          { 
            cache: 'no-store',
            headers: {
              'ngrok-skip-browser-warning': '1',
            }
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

        setHistory(payload as HistoryResponse);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : 'Unable to load history.');
      } finally {
        setLoading(false);
      }
    };

    void loadHistory();
  }, [userId]);

  const tickets = useMemo(() => history?.tickets ?? [], [history]);

  const fallbackSummary = useMemo<HistorySummary>(() => {
    const statusCounts: Record<string, number> = { won: 0, lost: 0, pending: 0 };
    let totalSpent = 0;
    let totalWinnings = 0;

    for (const ticket of tickets) {
      const normalizedStatus = (ticket.status || 'pending').toLowerCase();
      if (normalizedStatus in statusCounts) {
        statusCounts[normalizedStatus] += 1;
      } else {
        statusCounts.pending += 1;
      }

      const combinationsCount = toNumber(ticket.combinations_count);
      totalSpent += combinationsCount > 0 ? combinationsCount : 1;
      totalWinnings += toNumber(ticket.winning_amount);
    }

    return {
      total_tickets: tickets.length,
      total_spent: totalSpent,
      total_winnings: totalWinnings,
      active_tickets: statusCounts.pending,
      status_counts: statusCounts,
      game_type_counts: {},
      match_counts: {},
    };
  }, [tickets]);

  const summary = history?.summary || fallbackSummary;

  const filteredAndSortedTickets = useMemo(() => {
    const filtered = tickets.filter((ticket) => {
      const gameMatch = gameTypeFilter === 'ALL' || ticket.game_type === gameTypeFilter;
      const statusMatch = statusFilter === 'ALL' || ticket.status.toLowerCase() === statusFilter;
      return gameMatch && statusMatch;
    });

    return sortTickets(filtered, sortBy);
  }, [tickets, gameTypeFilter, statusFilter, sortBy]);

  const toggleExpandedTicket = (ticket: TicketRecord) => {
    if (ticket.game_type !== 'TOTO') return;
    setExpandedTicketId((current) => (current === ticket.id ? null : ticket.id));
  };

  return (
    <>
      <Navigation />

      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
        <div className="mx-auto max-w-6xl space-y-8">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Ticket History Dashboard</h1>
            <p className="text-gray-900">
              Track your uploaded 4D and TOTO tickets, auto-evaluated outcomes, and detailed winning sets.
            </p>
          </div>

          <div className="grid gap-6 md:grid-cols-3">
            <div className="bg-white rounded-lg shadow-lg p-6 border border-blue-100">
              <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Total Spent</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{formatMoney(summary.total_spent)}</p>
              <p className="mt-1 text-xs text-gray-900">Estimated at SGD 1 per combination</p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6 border border-green-100">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-900">Total Won</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{formatMoney(summary.total_winnings)}</p>
              <p className="mt-1 text-xs text-gray-900">From evaluated winning tickets</p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6 border border-amber-100">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-900">Active Tickets</p>
              <p className="mt-2 text-2xl font-bold text-gray-900">{summary.active_tickets}</p>
              <p className="mt-1 text-xs text-gray-900">Still pending draw outcomes</p>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-6 md:p-6 border border-blue-100">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label className="text-sm font-medium text-gray-900">
                Game Type
                <select
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-blue-200 focus:ring"
                  value={gameTypeFilter}
                  onChange={(event) => setGameTypeFilter(event.target.value as GameTypeFilter)}
                >
                  <option value="ALL">All Games</option>
                  <option value="4D">4D</option>
                  <option value="TOTO">TOTO</option>
                </select>
              </label>

              <label className="text-sm font-medium text-gray-900">
                Status
                <select
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-blue-200 focus:ring"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                >
                  <option value="ALL">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="won">Won</option>
                  <option value="lost">Lost</option>
                </select>
              </label>

              <label className="text-sm font-medium text-gray-900">
                Sort By
                <select
                  className="mt-1 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-blue-200 focus:ring"
                  value={sortBy}
                  onChange={(event) => setSortBy(event.target.value as SortBy)}
                >
                  <option value="draw_date_desc">Draw Date (Newest)</option>
                  <option value="prize_amount_desc">Prize Amount (Highest)</option>
                </select>
              </label>
            </div>
          </div>

          {loading && (
            <div className="bg-white rounded-lg shadow-lg p-8 border border-blue-100">
              <p className="text-sm text-gray-800">Loading ticket history...</p>
            </div>
          )}

          {!loading && error && (
            <div className="bg-gradient-to-r from-red-50 to-orange-50 rounded-lg border-2 border-red-300 p-5">
              <p className="text-sm font-semibold text-rose-700">Unable to load history</p>
              <p className="mt-1 text-sm text-rose-600">{error}</p>
            </div>
          )}

          {!loading && !error && filteredAndSortedTickets.length === 0 && (
            <div className="bg-white rounded-lg shadow-lg p-8 border border-blue-100">
              <p className="text-sm text-gray-800">No tickets match your selected filters.</p>
            </div>
          )}

          {!loading && !error && filteredAndSortedTickets.length > 0 && (
            <>
              <div className="space-y-5 md:hidden">
                {filteredAndSortedTickets.map((ticket) => {
                  const isExpanded = expandedTicketId === ticket.id;
                  const isToto = ticket.game_type === 'TOTO';

                  return (
                    <div
                      key={ticket.id}
                      className="overflow-hidden rounded-lg border border-blue-100 bg-white shadow-lg"
                    >
                      <div className="space-y-4 p-6">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-4">
                              <span
                                className={`rounded-full px-2 py-1 text-sm font-semibold ring-1 ${gameTypeClass(
                                  ticket.game_type
                                )}`}
                              >
                                {ticket.game_type}
                              </span>
                              <span
                                className={`rounded-full px-2 py-1 text-sm font-semibold ring-1 ${statusBadgeClass(
                                  ticket.status
                                )}`}
                              >
                                {ticket.status}
                              </span>
                            </div>
                            <p className="mt-3 text-sm font-semibold text-gray-900">{ticket.ticket_type}</p>
                            <p className="my-2 text-xs text-gray-900">Draw: {formatDrawDate(ticket.draw_date)}</p>
                          </div>

                          <div className="text-right">
                            <p className="text-xs text-gray-900">Prize Amount</p>
                            <p className="text-sm font-bold text-gray-900">{formatMoney(ticket.winning_amount)}</p>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-1.5 py-2">
                          {(ticket.selected_numbers || []).map((number, index) => (
                            <span
                              key={`${ticket.id}-mobile-number-${index}`}
                              className="rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold font-mono text-blue-900"
                            >
                              {number}
                            </span>
                          ))}
                        </div>

                        {isToto && (
                          <button
                            type="button"
                            className="w-full rounded-lg border border-blue-300 bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700"
                            onClick={() => toggleExpandedTicket(ticket)}
                          >
                            {isExpanded ? 'Hide TOTO Details' : 'Show TOTO Details'}
                          </button>
                        )}
                      </div>

                      {isExpanded && isToto && (
                        <div className="border-t border-blue-100 p-5">
                          <TotoDetailPanel ticket={ticket} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="hidden overflow-hidden rounded-lg border border-blue-100 bg-white shadow-lg md:block">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-blue-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Game</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Draw Date</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Ticket</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Numbers</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-800">Prize Tier</th>
                      <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-800">Won</th>
                      <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wide text-gray-800">Details</th>
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-gray-100">
                    {filteredAndSortedTickets.map((ticket) => {
                      const isExpanded = expandedTicketId === ticket.id;
                      const isToto = ticket.game_type === 'TOTO';

                      return (
                        <Fragment key={ticket.id}>
                          <tr className="hover:bg-blue-50/70">
                            <td className="px-4 py-3 text-sm text-gray-900">
                              <span
                                className={`rounded-full px-2 py-1 text-sm font-semibold ring-1 ${gameTypeClass(
                                  ticket.game_type
                                )}`}
                              >
                                {ticket.game_type}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">{formatDrawDate(ticket.draw_date)}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">{ticket.ticket_type}</td>
                            <td className="px-4 py-3 text-sm text-gray-900">
                              {(ticket.selected_numbers || []).join(', ')}
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">
                              <span
                                className={`rounded-full px-2 py-1 text-sm font-semibold ring-1 ${statusBadgeClass(
                                  ticket.status
                                )}`}
                              >
                                {ticket.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900">{ticket.prize_tier || '-'}</td>
                            <td className="px-4 py-3 text-right text-sm font-semibold text-gray-900">
                              {formatMoney(ticket.winning_amount)}
                            </td>
                            <td className="px-4 py-3 text-center">
                              {isToto ? (
                                <button
                                  type="button"
                                  className="rounded-md border border-blue-300 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700"
                                  onClick={() => toggleExpandedTicket(ticket)}
                                >
                                  {isExpanded ? 'Hide' : 'Expand'}
                                </button>
                              ) : (
                                <span className="text-xs text-gray-900">-</span>
                              )}
                            </td>
                          </tr>

                          {isExpanded && isToto && (
                            <tr>
                              <td className="bg-blue-50 px-4 py-5" colSpan={8}>
                                <TotoDetailPanel ticket={ticket} />
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}

