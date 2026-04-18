import { DecisionReport } from '../App';

interface ReportSectionsProps {
  report: DecisionReport;
}

export function ReportSections({ report }: ReportSectionsProps) {
  return (
    <div className="space-y-5">
      {/* 1. Situation - Hero card */}
      <section id="situation" className="col-span-2 p-10 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[32px] shadow-[0_8px_32px_rgba(0,0,0,0.06)]">
        <h2 className="text-xl text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
          Situation
        </h2>
        <p className="text-base text-gray-700 leading-relaxed" style={{ fontWeight: 400, lineHeight: '1.7' }}>
          {report.situation}
        </p>
      </section>

      {/* Grid layout for other sections */}
      <div className="grid grid-cols-2 gap-5">

        {/* 2. Insights */}
        <section id="insights" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Insights
          </h2>
          <div className="space-y-3 text-sm">
            {report.insights.decisionType && (
              <div className="flex gap-2">
                <span className="text-gray-500" style={{ fontWeight: 500 }}>Decision type:</span>
                <span className="text-gray-900" style={{ fontWeight: 400 }}>{report.insights.decisionType}</span>
              </div>
            )}
            {report.insights.timePressure && (
              <div className="flex gap-2">
                <span className="text-gray-500" style={{ fontWeight: 500 }}>Time pressure:</span>
                <span className="text-gray-900" style={{ fontWeight: 400 }}>{report.insights.timePressure}</span>
              </div>
            )}
            {report.insights.stress && (
              <div className="flex gap-2">
                <span className="text-gray-500" style={{ fontWeight: 500 }}>Stress/workload:</span>
                <span className="text-gray-900" style={{ fontWeight: 400 }}>{report.insights.stress}</span>
              </div>
            )}
            {report.insights.biasRisks && report.insights.biasRisks.length > 0 && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Bias risks:</div>
                <ul className="space-y-1.5 ml-4">
                  {report.insights.biasRisks.map((risk, i) => (
                    <li key={i} className="text-gray-900 list-disc" style={{ fontWeight: 400 }}>{risk}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.insights.memoryPatterns && report.insights.memoryPatterns.length > 0 && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Memory patterns:</div>
                <ul className="space-y-1.5 ml-4">
                  {report.insights.memoryPatterns.map((pattern, i) => (
                    <li key={i} className="text-gray-900 list-disc" style={{ fontWeight: 400 }}>{pattern}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        {/* 3. Options */}
        <section id="options" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Options
          </h2>
          <div className="space-y-4">
            {report.options.map((option) => (
              <div key={option.id} className="pb-4 border-b border-gray-200/40 last:border-0 last:pb-0">
                <div className="text-xs text-gray-400 font-mono mb-1" style={{ fontWeight: 500 }}>
                  [{option.id}]
                </div>
                <div className="text-sm text-gray-900 mb-1.5" style={{ fontWeight: 500 }}>{option.name}</div>
                <div className="text-sm text-gray-600 leading-relaxed" style={{ fontWeight: 400 }}>{option.description}</div>
              </div>
            ))}
          </div>
        </section>

        {/* 4. Trade-offs */}
        <section id="tradeoffs" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Trade-offs
          </h2>
          {report.tradeoffs ? (
            <div className="overflow-x-auto -mx-2">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200/40">
                    <th className="text-left py-3 px-3 text-xs uppercase tracking-wider text-gray-500" style={{ fontWeight: 600 }}>Option</th>
                    {report.tradeoffs.headers.map((header) => (
                      <th key={header} className="text-center py-3 px-3 text-xs uppercase tracking-wider text-gray-500" style={{ fontWeight: 600 }}>
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {report.tradeoffs.rows.map((row) => (
                    <tr key={row.optionId} className="border-b border-gray-200/40 last:border-0">
                      <td className="py-4 px-3 text-sm text-gray-900" style={{ fontWeight: 400 }}>{row.optionName}</td>
                      {report.tradeoffs!.headers.map((header) => (
                        <td key={header} className="text-center py-4 px-3 text-sm text-gray-900" style={{ fontWeight: 500 }}>
                          {row.scores[header]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-gray-500" style={{ fontWeight: 400 }}>No evaluation scores available</p>
          )}
        </section>

        {/* 5. Recommendation */}
        <section id="recommendation" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Recommendation
          </h2>
          <p className="text-sm text-gray-700 leading-relaxed mb-5" style={{ fontWeight: 400, lineHeight: '1.7' }}>
            {report.recommendation.reasoning}
          </p>
          <div className="pt-4 border-t border-gray-200/40">
            <div className="text-sm">
              <span className="text-gray-500" style={{ fontWeight: 500 }}>Chosen option: </span>
              <span className="text-gray-900" style={{ fontWeight: 600 }}>{report.recommendation.chosenOption}</span>
            </div>
          </div>
        </section>

        {/* 6. Actions */}
        <section id="actions" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Actions
          </h2>
          <ul className="space-y-4">
            {report.actions.map((action, i) => (
              <li key={i} className="flex items-start gap-4">
                <span className="w-6 h-6 mt-0.5 flex items-center justify-center bg-gradient-to-br from-purple-500 to-blue-500 text-white rounded-full text-xs flex-shrink-0 shadow-sm" style={{ fontWeight: 600 }}>
                  {i + 1}
                </span>
                <div className="flex-1">
                  <div className="text-sm text-gray-900 leading-relaxed" style={{ fontWeight: 400 }}>{action.text}</div>
                  {action.deadline && (
                    <div className="text-xs text-gray-500 mt-1.5" style={{ fontWeight: 500 }}>Due: {action.deadline}</div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </section>

        {/* 7. Reflection */}
        <section id="reflection" className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)]">
          <h2 className="text-base text-gray-900 mb-5 tracking-tight" style={{ fontWeight: 600 }}>
            Reflection
          </h2>
          <div className="space-y-4 text-sm">
            {report.reflection.possibleErrors && report.reflection.possibleErrors.length > 0 && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Possible errors:</div>
                <ul className="space-y-1.5 ml-4">
                  {report.reflection.possibleErrors.map((error, i) => (
                    <li key={i} className="text-gray-900 list-disc leading-relaxed" style={{ fontWeight: 400 }}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.reflection.uncertaintySources && report.reflection.uncertaintySources.length > 0 && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Uncertainty sources:</div>
                <ul className="space-y-1.5 ml-4">
                  {report.reflection.uncertaintySources.map((source, i) => (
                    <li key={i} className="text-gray-900 list-disc leading-relaxed" style={{ fontWeight: 400 }}>{source}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.reflection.informationGaps && report.reflection.informationGaps.length > 0 && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Information gaps:</div>
                <ul className="space-y-1.5 ml-4">
                  {report.reflection.informationGaps.map((gap, i) => (
                    <li key={i} className="text-gray-900 list-disc leading-relaxed" style={{ fontWeight: 400 }}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}
            {report.reflection.selfImprovement && (
              <div>
                <div className="text-gray-500 mb-2" style={{ fontWeight: 500 }}>Self-improvement:</div>
                <p className="text-gray-900 leading-relaxed" style={{ fontWeight: 400 }}>{report.reflection.selfImprovement}</p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
