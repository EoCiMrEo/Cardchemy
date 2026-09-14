import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import JoinCourse from './pages/JoinCourse';
import Dashboard from './pages/Dashboard';
import SubjectDetails from './pages/instructor/SubjectDetails';
import SetView from './pages/instructor/SetView';
import StudentSubjectDetails from './pages/student/StudentSubjectDetails';
import StudyMode from './pages/student/StudyMode';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';

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

function RoleRoute({ children, role }: { children: React.ReactNode; role: 'instructor' | 'student' }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to="/dashboard" replace />;
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
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          
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
              <RoleRoute role="instructor">
                <div className="min-h-screen bg-gray-50">
                    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                        <SetView />
                    </main>
                </div>
              </RoleRoute>
            }
          />

          <Route
            path="/study/:id"
            element={
              <RoleRoute role="student">
                <StudyMode />
              </RoleRoute>
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
