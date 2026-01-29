import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { subjectService } from "@/services/subjects";
import { Loader2, CheckCircle2, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function JoinCourse() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const { user, isLoading: authLoading } = useAuth();
  
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");
  const [courseName, setCourseName] = useState("");

  useEffect(() => {
    if (authLoading) return;

    // If not logged in, redirect to register with token
    if (!user) {
      navigate(`/register?token=${token}`);
      return;
    }

    // If logged in, join the course
    if (token) {
      joinCourse();
    } else {
      setStatus("error");
      setMessage("No invite token provided");
    }
  }, [user, authLoading, token]);

  const joinCourse = async () => {
    try {
      const result = await subjectService.joinCourse(token!);
      setStatus("success");
      setCourseName(result.subject_name);
      setMessage(result.message);
      
      // Redirect to dashboard after 2 seconds
      setTimeout(() => navigate("/dashboard"), 2000);
    } catch (err: any) {
      setStatus("error");
      setMessage(err.response?.data?.detail || "Failed to join course");
    }
  };

  if (authLoading || status === "loading") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <Loader2 className="h-10 w-10 animate-spin mx-auto text-primary" />
          <p className="mt-4 text-muted-foreground">Joining course...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader className="text-center">
          {status === "success" ? (
            <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto mb-4" />
          ) : (
            <XCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          )}
          <CardTitle className="text-2xl">
            {status === "success" ? "Course Joined!" : "Join Failed"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-4">
          {status === "success" ? (
            <>
              <p className="text-lg font-medium text-green-600">{courseName}</p>
              <p className="text-muted-foreground">Redirecting to dashboard...</p>
            </>
          ) : (
            <>
              <p className="text-destructive">{message}</p>
              <Button onClick={() => navigate("/dashboard")} className="w-full">
                Go to Dashboard
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
