import { createContext, useContext } from 'react';

// Opening a page of the filing is needed from flags, the map, tables and chat; one context avoids prop chains.
export const ViewerContext = createContext({ open: () => {} });
export const useViewer = () => useContext(ViewerContext);

export const SEVERITY_LABEL = { high: 'Look closely', medium: 'Worth reading', info: 'For context', ok: 'Reassuring' };
