export function TableOfContents() {
  const sections = [
    { id: 'situation', label: 'Situation' },
    { id: 'insights', label: 'Insights' },
    { id: 'options', label: 'Options' },
    { id: 'tradeoffs', label: 'Trade-offs' },
    { id: 'recommendation', label: 'Recommendation' },
    { id: 'actions', label: 'Actions' },
    { id: 'reflection', label: 'Reflection' }
  ];

  const scrollToSection = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="sticky top-12 h-fit w-[180px]">
      <div className="space-y-1">
        <div className="text-[12px] text-[#86868b] mb-3 px-3">Contents</div>
        {sections.map((section) => (
          <button
            key={section.id}
            onClick={() => scrollToSection(section.id)}
            className="w-full text-left px-3 py-1.5 text-[13px] text-[#1d1d1f] hover:bg-[#f5f5f7] rounded-[6px] transition-colors"
          >
            {section.label}
          </button>
        ))}
      </div>
    </div>
  );
}
