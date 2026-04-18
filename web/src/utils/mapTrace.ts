/**
 * Map backend `DecisionTrace` JSON (from `/api/run`) to UI `DecisionReport`.
 */
import type { DecisionReport } from '../app/App';

interface TraceUserState {
  raw_input: string;
  decision_type: string;
  time_pressure: string;
  stress_level: number;
  workload: number;
}

interface TraceOption {
  option_id: string;
  name: string;
  description: string;
}

interface TraceEvaluation {
  option_id: string;
  expected_value_score: number;
  risk_score: number;
  regret_score: number;
  uncertainty_score: number;
  goal_alignment_score: number;
}

interface TraceRecommendation {
  chosen_option_id: string;
  reasoning: string;
  next_actions: Array<{ action: string; deadline?: string | null }>;
}

interface TraceReflection {
  possible_errors: string[];
  uncertainty_sources: string[];
  information_gaps: string[];
  self_improvement_signal: string;
}

interface TraceRationality {
  detected_biases: string[];
}

interface TraceMemory {
  behavioral_patterns: string[];
}

export function mapTraceToReport(trace: Record<string, unknown>): DecisionReport {
  const us = trace.user_state as TraceUserState;
  const rationality = trace.rationality as TraceRationality;
  const memory = trace.memory as TraceMemory;
  const evaluations = (trace.evaluations as TraceEvaluation[]) ?? [];
  const options = (trace.options as TraceOption[]) ?? [];
  const rec = trace.recommendation as TraceRecommendation;
  const refl = trace.reflection as TraceReflection;

  const evalById = new Map(evaluations.map((e) => [e.option_id, e]));

  const rows = options.map((opt) => {
    const ev = evalById.get(opt.option_id);
    return {
      optionId: opt.option_id,
      optionName: opt.name,
      scores: ev
        ? {
            EV: Number(ev.expected_value_score.toFixed(1)),
            Risk: Number(ev.risk_score.toFixed(1)),
            Regret: Number(ev.regret_score.toFixed(1)),
            Uncertainty: Number(ev.uncertainty_score.toFixed(1)),
            GoalAlign: Number(ev.goal_alignment_score.toFixed(1)),
          }
        : {},
    };
  });

  const hasScores = rows.length > 0 && rows.some((r) => Object.keys(r.scores).length > 0);

  return {
    situation: us.raw_input,
    insights: {
      decisionType: us.decision_type,
      timePressure: us.time_pressure,
      stress: `${us.stress_level}/10, ${us.workload}/10`,
      biasRisks: rationality.detected_biases?.length ? rationality.detected_biases : undefined,
      memoryPatterns: memory.behavioral_patterns?.slice(0, 3),
    },
    options: options.map((o) => ({
      id: o.option_id,
      name: o.name,
      description: o.description,
    })),
    tradeoffs: hasScores
      ? {
          headers: ['EV', 'Risk', 'Regret', 'Uncertainty', 'GoalAlign'],
          rows,
        }
      : undefined,
    recommendation: {
      reasoning: rec.reasoning,
      chosenOption: rec.chosen_option_id,
    },
    actions: (rec.next_actions ?? []).map((a) => ({
      text: a.action,
      deadline: a.deadline ?? undefined,
    })),
    reflection: {
      possibleErrors: refl.possible_errors?.slice(0, 10),
      uncertaintySources: refl.uncertainty_sources?.slice(0, 10),
      informationGaps: refl.information_gaps?.slice(0, 10),
      selfImprovement: refl.self_improvement_signal,
    },
  };
}
