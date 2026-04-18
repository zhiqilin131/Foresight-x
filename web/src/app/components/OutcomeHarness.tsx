import { useState } from 'react';

interface OutcomeHarnessProps {
  decisionId: string;
  onClose: () => void;
}

export function OutcomeHarness({ decisionId, onClose }: OutcomeHarnessProps) {
  const [followedRecommendation, setFollowedRecommendation] = useState<boolean | null>(null);
  const [whatHappened, setWhatHappened] = useState('');
  const [outcomeQuality, setOutcomeQuality] = useState<number | null>(null);
  const [wouldReverse, setWouldReverse] = useState<boolean | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (
      followedRecommendation === null ||
      !whatHappened.trim() ||
      outcomeQuality === null ||
      wouldReverse === null
    ) {
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await fetch('/api/record-outcome', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision_id: decisionId,
          user_took_recommended_action: followedRecommendation,
          actual_outcome: whatHappened.trim(),
          user_reported_quality: outcomeQuality,
          reversed_later: wouldReverse,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || res.statusText);
      }
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-xl flex items-center justify-center z-50 px-4">
      <div className="bg-white/90 backdrop-blur-2xl rounded-[32px] shadow-2xl w-full max-w-[580px] border border-white/80">
        <div className="p-10 border-b border-gray-200/40">
          <h2 className="text-2xl text-gray-900 tracking-tight mb-2" style={{ fontWeight: 700 }}>
            Record Outcome
          </h2>
          <p className="text-base text-gray-600" style={{ fontWeight: 400 }}>
            Decision ID: <span className="font-mono text-sm">{decisionId}</span>
          </p>
          <p className="text-base text-gray-600 mt-2" style={{ fontWeight: 400 }}>
            Help improve future recommendations by sharing what happened.
          </p>
        </div>

        {submitError && (
          <div className="px-10 pt-4 text-sm text-red-700 bg-red-50/90">{submitError}</div>
        )}

        <div className="p-10 space-y-7">
          <div className="space-y-4">
            <label className="block text-sm text-gray-900" style={{ fontWeight: 500 }}>
              Did you take the recommended action?
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setFollowedRecommendation(true)}
                className={`flex-1 px-4 py-3 rounded-full border text-[14px] transition-all ${
                  followedRecommendation === true
                    ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white border-transparent shadow-lg'
                    : 'bg-white/60 text-gray-900 border-white/80 hover:bg-white/80'
                }`}
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() => setFollowedRecommendation(false)}
                className={`flex-1 px-4 py-3 rounded-full border text-[14px] transition-all ${
                  followedRecommendation === false
                    ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white border-transparent shadow-lg'
                    : 'bg-white/60 text-gray-900 border-white/80 hover:bg-white/80'
                }`}
              >
                No
              </button>
            </div>
          </div>

          <div className="space-y-4">
            <label htmlFor="what-happened" className="block text-sm text-gray-900" style={{ fontWeight: 500 }}>
              What actually happened?
            </label>
            <textarea
              id="what-happened"
              value={whatHappened}
              onChange={(e) => setWhatHappened(e.target.value)}
              placeholder="Describe the outcome..."
              className="w-full min-h-[120px] px-5 py-4 bg-white/70 border border-gray-200/60 rounded-3xl resize-none focus:outline-none focus:ring-2 focus:ring-purple-400/50 focus:border-transparent transition-all text-base text-gray-900 placeholder:text-gray-400 leading-relaxed shadow-sm"
              style={{ fontWeight: 400 }}
            />
          </div>

          <div className="space-y-4">
            <label className="block text-sm text-gray-900" style={{ fontWeight: 500 }}>
              Outcome quality (1–5)
            </label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((rating) => (
                <button
                  type="button"
                  key={rating}
                  onClick={() => setOutcomeQuality(rating)}
                  className={`flex-1 py-3 rounded-full border text-[14px] transition-all ${
                    outcomeQuality === rating
                      ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white border-transparent shadow-lg'
                      : 'bg-white/60 text-gray-900 border-white/80 hover:bg-white/80'
                  }`}
                >
                  {rating}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            <label className="block text-sm text-gray-900" style={{ fontWeight: 500 }}>
              Did you reverse this later?
            </label>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setWouldReverse(true)}
                className={`flex-1 px-4 py-3 rounded-full border text-[14px] transition-all ${
                  wouldReverse === true
                    ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white border-transparent shadow-lg'
                    : 'bg-white/60 text-gray-900 border-white/80 hover:bg-white/80'
                }`}
              >
                Yes
              </button>
              <button
                type="button"
                onClick={() => setWouldReverse(false)}
                className={`flex-1 px-4 py-3 rounded-full border text-[14px] transition-all ${
                  wouldReverse === false
                    ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white border-transparent shadow-lg'
                    : 'bg-white/60 text-gray-900 border-white/80 hover:bg-white/80'
                }`}
              >
                No
              </button>
            </div>
          </div>
        </div>

        <div className="p-8 border-t border-gray-200/40 flex gap-4">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-8 py-4 bg-white/70 text-gray-700 border border-gray-200/60 rounded-full hover:bg-white/90 hover:shadow-lg transition-all text-base"
            style={{ fontWeight: 500 }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={
              submitting ||
              followedRecommendation === null ||
              !whatHappened.trim() ||
              outcomeQuality === null ||
              wouldReverse === null
            }
            className="flex-1 px-8 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white rounded-full hover:shadow-2xl hover:shadow-purple-500/30 disabled:from-gray-300 disabled:to-gray-300 disabled:cursor-not-allowed transition-all text-base"
            style={{ fontWeight: 600 }}
          >
            {submitting ? 'Saving…' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  );
}
