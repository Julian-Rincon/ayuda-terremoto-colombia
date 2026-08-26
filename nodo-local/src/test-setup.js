import 'fake-indexeddb/auto'

// Matchers de jest-dom (toBeInTheDocument, toBeDisabled, etc.) para los tests
// de componentes React. Extender `expect` es inocuo para los tests de lógica
// pura que corren en entorno 'node' (db.test.js, sync.test.js): no tocan el
// DOM, así que nunca invocan estos matchers.
import '@testing-library/jest-dom/vitest'
