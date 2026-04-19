import { useNavigate } from 'react-router';
import { History, MessageCircleHeart, UserCircle } from 'lucide-react';

const btnClass =
  'inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full text-sm ' +
  'bg-white/80 backdrop-blur-sm border border-white/90 text-gray-800 shadow-sm ' +
  'hover:bg-white hover:shadow-md hover:border-purple-200/80 transition-all ' +
  'focus:outline-none focus:ring-2 focus:ring-purple-400/40';

export function MainNavButtons() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-wrap justify-center gap-3 mb-8">
      <button type="button" onClick={() => navigate('/reflect')} className={btnClass} style={{ fontWeight: 600 }}>
        <MessageCircleHeart className="w-4 h-4 text-purple-600 shrink-0" aria-hidden />
        Shadow self
      </button>
      <button type="button" onClick={() => navigate('/history')} className={btnClass} style={{ fontWeight: 600 }}>
        <History className="w-4 h-4 text-purple-600 shrink-0" aria-hidden />
        History
      </button>
      <button type="button" onClick={() => navigate('/profile')} className={btnClass} style={{ fontWeight: 600 }}>
        <UserCircle className="w-4 h-4 text-purple-600 shrink-0" aria-hidden />
        Profile
      </button>
    </div>
  );
}
