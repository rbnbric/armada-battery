/// Minimal live production for Battery's two-stage AI Hub decision path.
Class Battery.Interop.Production Extends Ens.Production
{
XData ProductionDefinition
{
<Production Name="Battery.Interop.Production" LogGeneralTraceEvents="true">
  <Description>Evidence-bound binary review and contradiction investigation</Description>
  <ActorPoolSize>1</ActorPoolSize>
  <Item Name="Battery.Intake" ClassName="Battery.Interop.IntakeService" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.CaseProcess" ClassName="Battery.Interop.SolverProcess" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.Review" ClassName="Battery.Interop.CaseProcess" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.Evidence" ClassName="Battery.Interop.EvidenceOperation" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.Agent" ClassName="Battery.Interop.AgentOperation" PoolSize="1" Enabled="true" Foreground="false"/>
</Production>
}
}
