Class Battery.Test.SolverProduction Extends Ens.Production
{
XData ProductionDefinition
{
<Production Name="Battery.Test.SolverProduction" LogGeneralTraceEvents="true">
<ActorPoolSize>1</ActorPoolSize>
<Item Name="Battery.Intake" ClassName="Battery.Interop.IntakeService" PoolSize="1" Enabled="true" Foreground="false"/>
<Item Name="Battery.CaseProcess" ClassName="Battery.Interop.SolverProcess" PoolSize="1" Enabled="true" Foreground="false"/>
<Item Name="Battery.Review" ClassName="Battery.Interop.CaseProcess" PoolSize="1" Enabled="true" Foreground="false"/>
<Item Name="Battery.Evidence" ClassName="Battery.Test.SolverEvidence" PoolSize="1" Enabled="true" Foreground="false"/>
<Item Name="Battery.Agent" ClassName="Battery.Test.SolverAgent" PoolSize="1" Enabled="true" Foreground="false"/>
</Production>
}
}
