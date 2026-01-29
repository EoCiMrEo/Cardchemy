import { BrowserRouter as Router, Routes, Route, Navigate, useParams } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import JoinCourse from './pages/JoinCourse';
import Dashboard from './pages/Dashboard';
import SubjectDetails from './pages/instructor/SubjectDetails';
import SetView from './pages/instructor/SetView';
import StudentDashboard from './pages/student/StudentDashboard';
import StudentSubjectDetails from './pages/student/StudentSubjectDetails';
import StudyMode from './pages/student/StudyMode';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" />;
  }

  return <>{children}</>;
}

function RoleBasedSubjectDetails() {
    const { user } = useAuth();
    if (user?.role === 'instructor') {
        return <SubjectDetails />;
    }
    return <StudentSubjectDetails />;
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/join" element={<JoinCourse />} />
          
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />

          <Route
            path="/subjects/:id"
            element={
              <ProtectedRoute>
                <div className="min-h-screen bg-gray-50">
                    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                        <RoleBasedSubjectDetails />
                    </main>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/sets/:id"
            element={
              <ProtectedRoute>
                <div className="min-h-screen bg-gray-50">
                    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                        <SetView />
                    </main>
                </div>
              </ProtectedRoute>
            }
          />

          <Route
            path="/study/:id"
            element={
              <ProtectedRoute>
                <StudyMode />
              </ProtectedRoute>
            }
          />
          
          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </AuthProvider>
    </Router>
  );
}

export default App;
