import { BrowserRouter } from 'react-router-dom';
import { AppRouter } from './pages/router';

function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  );
}

export default App;
