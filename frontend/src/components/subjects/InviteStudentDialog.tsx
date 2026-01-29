import { useState } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { subjectService } from "@/services/subjects"
import { Copy, Check, Loader2, Link as LinkIcon } from "lucide-react"

interface InviteStudentDialogProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    subjectId: string
    subjectName: string
}

export function InviteStudentDialog({ open, onOpenChange, subjectId, subjectName }: InviteStudentDialogProps) {
    const [expires, setExpires] = useState("24")
    const [loading, setLoading] = useState(false)
    const [inviteLink, setInviteLink] = useState("")
    const [copied, setCopied] = useState(false)

    const handleGenerate = async () => {
        try {
            setLoading(true)
            const result = await subjectService.generateInvite(subjectId, parseInt(expires))
            
            // Construct Link using current host
            const protocol = window.location.protocol
            const host = window.location.host
            const link = `${protocol}//${host}/join?token=${result.token}`
            
            setInviteLink(link)
            setCopied(false)
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    const handleCopy = () => {
        if (!inviteLink) return
        navigator.clipboard.writeText(inviteLink)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    const handleClose = () => {
        onOpenChange(false)
        setInviteLink("")
    }

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Invite Students</DialogTitle>
                    <DialogDescription>
                        Generate a link for students to join <strong>{subjectName}</strong>.
                    </DialogDescription>
                </DialogHeader>
                
                {!inviteLink ? (
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                             <label className="text-sm font-medium">Link Expiration</label>
                             <Select value={expires} onValueChange={setExpires}>
                                <SelectTrigger>
                                    <SelectValue placeholder="Select expiration" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="24">24 Hours</SelectItem>
                                    <SelectItem value="72">3 Days</SelectItem>
                                    <SelectItem value="168">7 Days</SelectItem>
                                    <SelectItem value="720">30 Days</SelectItem>
                                </SelectContent>
                             </Select>
                             <p className="text-xs text-muted-foreground">
                                Students must register using this link before it expires.
                             </p>
                        </div>
                        <Button onClick={handleGenerate} disabled={loading} className="w-full">
                            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <LinkIcon className="mr-2 h-4 w-4" />}
                            Generate Invite Link
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-4 py-4">
                         <div className="p-4 bg-green-50 rounded-lg text-center text-green-800 text-sm">
                             Link generated successfully!
                         </div>
                         <div className="flex items-center space-x-2">
                            <Input 
                                readOnly 
                                value={inviteLink} 
                                className="flex-1 font-mono text-xs bg-slate-50"
                                onClick={(e) => e.currentTarget.select()}
                            />
                            <Button size="icon" variant="outline" onClick={handleCopy}>
                                {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
                            </Button>
                         </div>
                         <Button variant="ghost" className="w-full" onClick={() => setInviteLink("")}>
                             Generate New Link
                         </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    )
}
