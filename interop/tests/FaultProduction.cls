Class Battery.Test.FaultProduction Extends Ens.Production
{
XData ProductionDefinition
{
<Production Name="Battery.Test.FaultProduction" LogGeneralTraceEvents="true">
  <ActorPoolSize>1</ActorPoolSize>
  <Item Name="Battery.Intake" ClassName="Battery.Interop.IntakeService" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.CaseProcess" ClassName="Battery.Test.FaultProcess" PoolSize="1" Enabled="true" Foreground="false"/>
  <Item Name="Battery.Agent" ClassName="Battery.Test.FaultOperation" PoolSize="1" Enabled="true" Foreground="false"/>
</Production>
}
}
