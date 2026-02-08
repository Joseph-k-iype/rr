import { useEffect, useState, useCallback, useRef } from 'react';
import type { AgentEvent } from '../types/agent';

const MAX_EVENTS = 200;
const TERMINAL_EVENTS = new Set(['workflow_complete', 'workflow_failed']);

export function useAgentEvents(sessionId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!sessionId) return;

    // Close any existing connection
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }

    const source = new EventSource(`/api/agent-events/stream/${sessionId}`);
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    const handler = (e: MessageEvent) => {
      try {
        const event: AgentEvent = JSON.parse(e.data);
        setEvents(prev => {
          const next = [...prev, event];
          // Cap events to prevent unbounded memory growth
          return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
        });

        // Close connection on terminal events
        if (TERMINAL_EVENTS.has(event.event_type)) {
          source.close();
          sourceRef.current = null;
          setConnected(false);
        }
      } catch {
        // ignore parse errors
      }
    };

    // Listen to all event types
    const eventTypes = [
      'agent_started', 'agent_completed', 'agent_failed',
      'phase_changed', 'analysis_progress', 'dictionary_progress',
      'validation_progress', 'cypher_progress', 'human_review_required',
      'workflow_complete', 'workflow_failed', 'heartbeat',
    ];

    eventTypes.forEach(type => source.addEventListener(type, handler));

    return () => {
      source.close();
      sourceRef.current = null;
      setConnected(false);
    };
  }, [sessionId]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { events, connected, clearEvents };
}
