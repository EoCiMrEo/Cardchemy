import { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppErrorBoundary } from './components/feedback/AppErrorBoundary';
import { copy } from './i18n/en';
import { ProtectedRoute, RoleRoute } from './components/auth/RouteGuards';

const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const JoinCourse = lazy(() => import('./pages/JoinCourse'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const SubjectDetails = lazy(() => import('./pages/instructor/SubjectDetails'));
const SetView = lazy(() => import('./pages/instructor/SetView'));
const StudentSubjectDetails = lazy(() => import('./pages/student/StudentSubjectDetails'));
const StudyMode = lazy(() => import('./pages/student/StudyMode'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const NotFound = lazy(() => import('./pages/NotFound'));

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
        <AppErrorBoundary>
          <Suspense fallback={<div className="flex min-h-dvh items-center justify-center" role="status">{copy.routing.loadingAccount}</div>}>
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
                    <div className="min-h-dvh bg-gray-50">
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
                    <div className="min-h-dvh bg-gray-50">
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
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </AppErrorBoundary>
      </AuthProvider>
    </Router>
  );
}

export default App;
