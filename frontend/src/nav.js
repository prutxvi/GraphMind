import { useEffect, useState } from 'react';

// A tiny History-API router: five routes don't justify a dependency.
export function navigate(to) {
  window.history.pushState({}, '', to);
  window.dispatchEvent(new PopStateEvent('popstate'));
  window.scrollTo(0, 0);
}

export function usePath() {
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  return path;
}

export function match(path) {
  let m;
  if (path === '/' || path === '') return { page: 'home' };
  if ((m = path.match(/^\/ipo\/([^/]+)\/?$/))) return { page: 'filing', id: decodeURIComponent(m[1]) };
  if ((m = path.match(/^\/entity\/(\d+)\/?$/))) return { page: 'entity', id: Number(m[1]) };
  if (path.startsWith('/method')) return { page: 'method' };
  if (path.startsWith('/add')) return { page: 'add' };
  return { page: 'missing' };
}
