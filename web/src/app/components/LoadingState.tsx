export function LoadingState() {
  return (
    <div className="space-y-5">
      {/* Situation skeleton - larger card */}
      <div className="p-10 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[32px] shadow-[0_8px_32px_rgba(0,0,0,0.06)] animate-pulse">
        <div className="h-5 w-28 bg-gray-200/60 rounded-full mb-5"></div>
        <div className="space-y-3">
          <div className="h-4 bg-gray-200/60 rounded-full w-full"></div>
          <div className="h-4 bg-gray-200/60 rounded-full w-5/6"></div>
          <div className="h-4 bg-gray-200/60 rounded-full w-4/6"></div>
        </div>
      </div>

      {/* Grid of section skeletons */}
      <div className="grid grid-cols-2 gap-5">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="p-7 bg-white/50 backdrop-blur-2xl border border-white/80 rounded-[28px] shadow-[0_4px_24px_rgba(0,0,0,0.04)] animate-pulse">
            <div className="h-4 w-24 bg-gray-200/60 rounded-full mb-5"></div>
            <div className="space-y-2.5">
              <div className="h-3 bg-gray-200/60 rounded-full w-full"></div>
              <div className="h-3 bg-gray-200/60 rounded-full w-4/5"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
