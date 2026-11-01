"""One-time mechanical extraction of the existing completion path."""
from pathlib import Path
p=Path('packages/platform_sdk/modular_platform/restore_executor.py')
s=p.read_text();start=s.index('            # The restored checkpoint may resurrect effects')
assert 'def _complete_restore(' not in s,'One-time source extraction already applied; never replay'
end=s.index('\n    def _resume_state',start)
tail=s[start:end]
assert tail.endswith("'operation_status':self.store.status(operation)}\n")
body='\n'.join(line[4:] if line.startswith('    ') else line for line in tail.splitlines())+'\n'
head="    def _complete_restore(self,decision,*,exact_hash,locks,directory,checkpoint,manifest,fresh,private_native_auth,dispatch_directory=None):\n        operation=decision['operation_id']\n"
s=s[:start]+"            return self._complete_restore(decision,exact_hash=exact_hash,locks=locks,directory=directory,checkpoint=checkpoint,manifest=manifest,fresh=fresh,private_native_auth=private_native_auth)\n\n"+head+body+s[end:]
s=s.replace("    def prepare(self,operation):\n        return RecoveryReviews(self.store).issue(self._restore_state(operation))", "    def prepare(self,operation):\n        directory=self.store.root/'recoveries'/operation\n        if directory.exists():\n            from .restore_continuation import RestoreContinuation\n            return RecoveryReviews(self.store).issue(RestoreContinuation(self).state(operation))\n        return RecoveryReviews(self.store).issue(self._restore_state(operation))")
s=s.replace("    def execute(self, decision, *, exact_hash, noninteractive=False):\n        operation = decision['operation_id']", "    def execute(self, decision, *, exact_hash, noninteractive=False):\n        if 'continuation' in decision:\n            from .restore_continuation import RestoreContinuation\n            return RestoreContinuation(self).execute(decision,exact_hash=exact_hash,noninteractive=noninteractive)\n        operation = decision['operation_id']",1)
s=s.replace("directory/'dispatch-fence',configuration=target,", "(dispatch_directory or directory)/'dispatch-fence',configuration=target,review_id=decision['review']['review_id'],",1)
s=s.replace("previous_release=digest,release_digest=digest,inventory_digest=restored['release_lock']['core_inventory_digest'])", "previous_release=digest,release_digest=digest,inventory_digest=restored['release_lock']['core_inventory_digest'],review_id=decision['review']['review_id'])",1)
p.write_text(s)
