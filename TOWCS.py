from random import randint
from decimal import Decimal
from math import ceil, floor
import time

"""
The Old World Combat Simulator (TOWCS)
Quick and dirty simulator of simple combat scenarios in Warhammer: The Old World
Author:		Víctor M. Nouvilas
Version:	0.1
Date:		2024/12/30

- One attacker unit, one defender unit.
- Initiative based on profile or forced by user (e.g. to simulate charges)
- Rolls to hit, wound, armour save, ward save, regeneration. No re-rolls (yet)
- Combat results
- Some special abilities:
	* Armour Bane
	* Poisoned Attacks
	* Extra Attacks
	* Unstable
"""

# Debug
global deb
deb = 0
def debug(*strings):
	if deb: print(*strings)

# Only show 2 decimal places
class D(Decimal):
    def __str__(self):
        return f'{self:.2f}'

# Weapon Class
class Weapon:
	def __init__(self, name, Sbonus=0, AP=0, AB=0, PA=0, EA=0):
		self.name=name
		self.Sbonus=Sbonus	# Bonus to Strength
		self.AP=AP			# Armour Penetration
		self.AB=AB			# Armour Bane
		self.PA=PA			# Poisoned Attacks (0=no, 1=yes)
		self.EA=EA			# Extra attacks
	
	def HW(AB=0,PA=0):
		return Weapon(name="Hand Weapons",AB=AB,PA=PA)
	
	def AHW(AB=0,PA=0):
		return Weapon(name="Two Hand Weapons",AB=AB,EA=1,PA=PA)
		
	def EW(PA=0):
		return Weapon(name="Ensorcelled Weapons",AP=1,PA=PA)
	
	def Halberd(PA=0):
		return Weapon(name="Halberds",Sbonus=1,AP=1,AB=1,PA=PA)
	
	def Spear(AB=0,PA=0):
		return Weapon(name="Thrusting Spears",AB=AB,PA=PA)
	
	def GW(PA=0):
		return Weapon(name="Great Weapons",Sbonus=2,AP=2,AB=1,PA=PA)
		

# Unit Class
class Unit:
	def __init__(self, name, Num, M, WS, BS, S, T, W, I, A, Ld, Sv=7, Ward=7, Reg=7, AddA=0, weapon=Weapon("Hand Weapons"), unstable=0, base=25):
		self.name=name
		self.Num=Num	# Number of models that can fight
		self.M=M		# Movement
		self.WS=WS		# Weapon Skill
		self.BS=BS		# Ballistic Skill
		self.S=S		# Strength
		self.T=T		# Toughness
		self.W=W		# Wounds
		self.I=I		# Initiative
		self.A=A		# Attacks
		self.Ld=Ld		# Leadership
		self.Sv=Sv		# Armour Save (Sv+)
		self.Ward=Ward	# Ward Save (Ward+)
		self.Reg=Reg	# Regeneration (Reg+)
		self.AddA=AddA	# Additional attacks (e.g. because of a Champion)
		self.weapon=weapon
		self.TotalAttacks=Num*(A+weapon.EA)+AddA
		self.unstable=unstable	# Unstable special rule (0=no, 1=yes)
		self.base=base	# Base size (e.g. 25mm)
	
	def StateTroops(Num, Sv=6, AddA=0, weapon=Weapon.HW()):
		return Unit("Empire State Troops", Num=Num, M=4, WS=3, BS=3, S=3, T=3, W=1, I=3, A=1, Ld=7, Sv=Sv, AddA=AddA, weapon=weapon)
	
	def Greatswords(Num, Sv=4, AddA=0, weapon=Weapon.GW()):
		return Unit("Empire Greatswords", Num=Num, M=4, WS=4, BS=3, S=3, T=3, W=1, I=3, A=1, Ld=8, Sv=Sv, AddA=AddA, weapon=weapon)
	
	def ChaosWarriors(Num, Sv=5, AddA=0, weapon=Weapon.EW()):
		return Unit("Chaos Warriors", Num=Num, M=4, WS=5, BS=3, S=4, T=4, W=1, I=4, A=1, Ld=8, Sv=Sv, AddA=AddA, weapon=weapon, base=30)
		
	def Chosen(Num, Sv=5, AddA=0, weapon=Weapon.EW()):
		return Unit("Chaos Chosen Warriors", Num=Num, M=4, WS=5, BS=3, S=4, T=4, W=1, I=4, A=2, Ld=9, Sv=Sv, Ward=6, AddA=AddA, weapon=weapon, base=30)
	
	def ChaosOgres(Num, Sv=5, AddA=0, weapon=Weapon.HW(AB=1)):
		return Unit("Chaos Ogres", Num=Num, M=6, WS=3, BS=2, S=4, T=4, W=3, I=2, A=3, Ld=7, Sv=Sv, AddA=AddA, weapon=weapon, base=40)
	
	def SkeletonWarriors(Num, Sv=6, AddA=0, weapon=Weapon.HW()):
		return Unit("Skeleton Warriors", Num=Num, M=4, WS=2, BS=2, S=3, T=3, W=1, I=2, A=1, Ld=5, Reg=6, unstable=1, Sv=Sv, AddA=AddA, weapon=weapon)
		
# To Hit Table
def Hit(atWS,defWS):
	if defWS > 2*atWS:
		result = 5
	elif atWS > 2*defWS:
		result = 2
	elif atWS > defWS and atWS <= 2*defWS:
		result = 3
	else:
		result = 4
	return result	

# To Wound Table
def Wound(S,T):
	if S == T:
		result = 4
	elif S == T+1:
		result = 3
	elif S == T-1:
		result = 5
	elif S > T+1:
		result = 2
	elif S < T-1 and T <= S+5:
		result = 6
	else:
		result = 7
	return result

# Dice rolls
def D6(mod=0):
	return max(1,min(6,randint(1,6)+mod))

def ND6(N,mod=0):
	rolls = []
	for i in range(N):
		rolls.append(D6(mod))
	return rolls

def Compare(rolls,target):
	return sum(1 for d in rolls if d >= target)

# One random instance of Combat
def Combat(Battacker, Bdefender, atBonus=0, defBonus=0, initiative=0, defendedObstacle=0, nDefendersInCombat=0):
	"""
	Inputs:
		attacker		: instance of Unit class
		defender		: instance of Unit class
		atBonus			: int. combat bonus for attacker unit (rank, standard, musician, etc.)
		defBonus		: int. combat bonus for defender unit (rank, standard, musician, etc.)
		initiative		: 0 = following profile initiatives, 1 = attacker first, 2 = defender first, 3 = simultaneous
		defendedObstacle: 1 = Attacker hits on 6s, strikes last, 0 = normal combat
		siegeTower		: 1 = Combat only with base contact and 1st adjacents (experimental rule), 0 = normal combat.
						  Attacker unit determines number of models in combat for defender.
		
	Outputs:
		[winner,	: 0 = draw, 1 = attacker, 2 = defender
		[scoreAt,	: Attacker combat score
		damageAt,	: Damage inflicted by attacker (including every save)
		deathsAt],	: Number of attacking models dead 
		[scoreDef,	: Defender combat score
		damageDef,	: Damage inflicted by defender (including every save)
		deathsDef]]	: Number of defending models dead
	"""
	
	if (initiative == 2 or (initiative == 0 and Battacker.I < Bdefender.I) or defendedObstacle):
		# Battle Defender is first
		attacker = Bdefender
		defender = Battacker
		switched=1
	else:
		# Battle Attacker is first or both simultaneous
		attacker = Battacker
		defender = Bdefender
		switched=0

	### First unit to attack
	
	totalDamage1 = 0
	Asaves1=0
	ABsaves1=0
	Wsaves1=0
	Rsaves1=0

	debug("First attacker:",attacker.name,"with",attacker.weapon.name)
	debug("")

	if switched:
		numAttacks = nDefendersInCombat*(attacker.A+attacker.weapon.EA)+attacker.AddA
	else:
		numAttacks = attacker.TotalAttacks
	
	debug("Number of attacks:",numAttacks)
	debug("")
	# Roll to Hit
	rolls = ND6(numAttacks)
	debug("Rolls to Hit:",rolls)
	target = Hit(attacker.WS,defender.WS)
	debug("Hitting on",target,"+")
	hits1 = Compare(rolls, target)
	debug("Hits:",hits1)
	if (attacker.weapon.PA == 1):
		poisonedHits1 = Compare(rolls, 6)
		debug("Poisoned Hits:",poisonedHits1)
	else:
		poisonedHits1 = 0
	debug("")
	
	if (hits1 > 0):
	
		# Roll to Wound
		rolls = ND6(hits1)
		debug("Rolls to Wound:",rolls)
		target = Wound(attacker.S+attacker.weapon.Sbonus,defender.T)
		debug("Wounding on",target,"+")
		wounds1 = Compare(rolls, target) + poisonedHits1
		debug("Wounds:",wounds1)
		debug("")
		# Armour Bane
		baneWounds1 = 0
		if (attacker.weapon.AB > 0):
			baneWounds1 = Compare(rolls, 6)
			debug("Armour bane ("+str(attacker.weapon.AB)+") wounds:",baneWounds1)
		
		if (wounds1 > 0):
		
			# Armour save
			if (defender.Sv + attacker.weapon.AP < 7):
				rolls = ND6(wounds1-baneWounds1)
				debug("Armour rolls:",rolls)
				target = defender.Sv+attacker.weapon.AP
				debug("Saving on",target,"+")
				Asaves1 = Compare(rolls, target)
			if (attacker.weapon.AB > 0 and defender.Sv + attacker.weapon.AP + attacker.weapon.AB < 7):
				rolls = ND6(baneWounds1)
				debug("Armour Bane rolls:",rolls)
				target = defender.Sv+attacker.weapon.AP + attacker.weapon.AB
				debug("Saving on",target,"+")
				ABsaves1 = Compare(rolls, target)
			Asaves1+=ABsaves1
			debug("Saves:",Asaves1)
			debug("")

			# Ward save
			if (defender.Ward < 7):
				rolls = ND6(wounds1-Asaves1)
				debug("Ward rolls:",rolls)
				target = defender.Ward
				debug("Saving on",target,"+")
				Wsaves1 = Compare(rolls, target)
				debug("Ward Saves:",Wsaves1)
				debug("")
			
			totalDamage1 = wounds1-Asaves1-Wsaves1
			debug("Total damage:",totalDamage1)
			debug("")
			
			# Regeneration
			if (defender.Reg < 7):
				rolls = ND6(totalDamage1)
				debug("Regeneration rolls:",rolls)
				target = defender.Reg
				debug("Saving on",target,"+")
				Rsaves1 = Compare(rolls, target)
				debug("Regeneration Saves:",Rsaves1)
				debug("")
	
	debug("-------")
	debug("")
	
	### Second unit to attack
	
	totalDamage2 = 0
	Asaves2=0
	ABsaves2=0
	Wsaves2=0
	Rsaves2=0
	
	if (initiative == 3 or (initiative == 0 and Battacker.I == Bdefender.I)):
		lostModels = 0
	else:
		lostModels = int((totalDamage1-Rsaves1)/defender.W)
	
	if (lostModels >= defender.Num):
		numAttacks = 0
	else:
		if switched:
			numAttacks = defender.TotalAttacks-defender.A*lostModels
		else:
			numAttacks = nDefendersInCombat*(defender.A+defender.weapon.EA)+defender.AddA-defender.A*lostModels

	debug("Second attacker:",defender.name,"with",defender.weapon.name)
	debug("")
	debug("Number of attacks:",numAttacks)
	debug("")
	if (numAttacks > 0):
		# Roll to Hit
		rolls = ND6(numAttacks)
		debug("Rolls to Hit:",rolls)
		if defendedObstacle:
			target = 6
		else:
			target = Hit(defender.WS,attacker.WS)
		debug("Hitting on",target,"+")
		hits2 = Compare(rolls, target)
		debug("Hits:",hits2)
		if (defender.weapon.PA == 1):
			poisonedHits2 = Compare(rolls, 6)
			debug("Poisoned Hits:",poisonedHits2)
		else:
			poisonedHits2 = 0
		debug("")
		
		if (hits2 > 0):
		
			# Roll to Wound
			rolls = ND6(hits2)
			debug("Rolls to Wound:",rolls)
			target = Wound(defender.S+defender.weapon.Sbonus,attacker.T)
			debug("Wounding on",target,"+")
			wounds2 = Compare(rolls, target) + poisonedHits2
			debug("Wounds:",wounds2)
			debug("")
			# Armour Bane
			baneWounds2 = 0
			if (defender.weapon.AB > 0):
				baneWounds2 = Compare(rolls, 6)
				debug("Armour bane ("+str(defender.weapon.AB)+") wounds:",baneWounds2)
			
			if (wounds2 > 0):
			
				# Armour save
				if (attacker.Sv + defender.weapon.AP < 7):
					rolls = ND6(wounds2-baneWounds2)
					debug("Armour rolls:",rolls)
					target = attacker.Sv + defender.weapon.AP
					debug("Saving on",target,"+")
					Asaves2 = Compare(rolls, target)
				if (defender.weapon.AB > 0 and attacker.Sv + defender.weapon.AP + defender.weapon.AB < 7):
					rolls = ND6(baneWounds2)
					debug("Armour Bane rolls:",rolls)
					target = attacker.Sv + defender.weapon.AP + defender.weapon.AB
					debug("Saving on",target,"+")
					ABsaves2 = Compare(rolls, target)
				Asaves2+=ABsaves2
				debug("Saves:",Asaves2)
				debug("")

				# Ward save
				if (attacker.Ward < 7):
					rolls = ND6(wounds2-Asaves2)
					debug("Ward rolls:",rolls)
					target = attacker.Ward
					debug("Saving on",target,"+")
					Wsaves2 = Compare(rolls, target)
					debug("Saves:",Wsaves2)
					debug("")
				
				totalDamage2 = wounds2-Asaves2-Wsaves2
				debug("Total damage:",totalDamage2)
				debug("")
				
				# Regeneration
				if (attacker.Reg < 7):
					rolls = ND6(totalDamage2)
					debug("Regeneration rolls:",rolls)
					target = attacker.Reg
					debug("Saving on",target,"+")
					Rsaves2 = Compare(rolls, target)
					debug("Regeneration Saves:",Rsaves2)
					debug("")
		
		debug("-------")

	debug("")
	debug("Combat Resolution:")
	# Combat Resolution	
	if (switched == 0):	
		scoreAt = totalDamage1 + atBonus
		scoreDef = totalDamage2 + defBonus
		damageAt = totalDamage1 - Rsaves1
		damageDef = totalDamage2 - Rsaves2
	else:
		scoreAt = totalDamage2 + atBonus
		scoreDef = totalDamage1 + defBonus
		damageAt = totalDamage2 - Rsaves2
		damageDef = totalDamage1 - Rsaves1
	crumbledAt = max(0,attacker.unstable*(scoreDef-scoreAt))
	crumbledDef = max(0,defender.unstable*(scoreAt-scoreDef))
	deathsAt = min(attacker.Num,int(damageDef/attacker.W)+crumbledAt)
	deathsDef = min(defender.Num,int(damageAt/defender.W)+crumbledDef)
	
	debug("  Attacker:",attacker.name)
	debug("    Score:",scoreAt)
	debug("    Effective Damage inflicted:",damageAt)
	if (attacker.unstable): debug("    Models crumbled:",crumbledAt)
	debug("    Total Models lost:",deathsAt)
	debug("  Defender:",defender.name)
	debug("    Score:",scoreDef)
	debug("    Effective Damage inflicted:",damageDef)
	if (defender.unstable): debug("    Models crumbled:",crumbledDef)
	debug("    Total Models lost:",deathsDef)
	# Winner
	if (scoreAt > scoreDef):
		winner = 1
		debug("  Winner: Attacker")
	elif (scoreAt < scoreDef):
		winner = 2
		debug("  Winner: Defender")
	else:
		winner = 0
		debug("  Winner: Draw")
	debug("")
	# Output
	return [winner,[scoreAt,damageAt,deathsAt],[scoreDef,damageDef,deathsDef]]



# Simulation of N combats
def Sim(Ncombats, Battacker, Bdefender, atBonus=0, defBonus=0, initiative=0, defendedObstacle=0, siegeTower=0):
	start_time = time.time()
	avScoreAt = 0
	avDamageAt = 0
	avDeathsAt = 0
	avScoreDef = 0
	avDamageDef = 0
	avDeathsDef = 0
	avDraw = 0
	avWinAt = 0
	avWinDef = 0
	
	if siegeTower:
		# Maximum number of defender models that fit in a segment of rampart.
		maxDefenders = floor(300 / Bdefender.base)
		# Minimum (max is min+1) number of defender models in base combat (if rampart full of defenders)
		nDefendersInCombat = min(Bdefender.Num,min(maxDefenders,2+ceil(Battacker.Num*Battacker.base/Bdefender.base)))
	else:
		nDefendersInCombat = Bdefender.Num
	
	#print("W, [AS,AD,AL], [DS,DD,DL]")
	for i in range(Ncombats):
		[winner,[scoreAt,damageAt,deathsAt],[scoreDef,damageDef,deathsDef]] = \
		Combat(Battacker, Bdefender, atBonus, defBonus, initiative, defendedObstacle, nDefendersInCombat)
		debug([winner,[scoreAt,damageAt,deathsAt],[scoreDef,damageDef,deathsDef]])
		debug("")
		avScoreAt += scoreAt
		avDamageAt += damageAt
		avDeathsAt += deathsAt
		avScoreDef += scoreDef
		avDamageDef += damageDef
		avDeathsDef += deathsDef
		if (winner == 0): avDraw += 1
		if (winner == 1): avWinAt += 1
		if (winner == 2): avWinDef += 1
	
	avScoreAt = avScoreAt / Ncombats
	avDamageAt = avDamageAt / Ncombats
	avDeathsAt = avDeathsAt / Ncombats
	avScoreDef = avScoreDef / Ncombats
	avDamageDef = avDamageDef / Ncombats
	avDeathsDef = avDeathsDef / Ncombats
	avDraw = avDraw / Ncombats
	avWinAt = avWinAt / Ncombats
	avWinDef = avWinDef / Ncombats
	
	print("Warhammer: The Old World(R) Combat Simulator (TOWCS)")
	print("")
	print("Combats simulated:",Ncombats)
	print("")
	print("Combat order:")
	if (initiative == 2 or (initiative == 0 and Battacker.I < Bdefender.I) or defendedObstacle):
		print("  Defender")
		print("  Attacker")
	if (defendedObstacle == 0 and (initiative == 1 or (initiative == 0 and Battacker.I > Bdefender.I))):
		print("  Attacker")
		print("  Defender")
	elif (defendedObstacle == 0 and (initiative == 3 or (initiative == 0 and Battacker.I == Bdefender.I))):
		print("  Simultaneous")
	
	if defendedObstacle:
		print("  (Defended Obstacle)")
	if siegeTower:
		print("  (Siege Tower experimental rules)")
	
	print("")
	print("Combat results:")
	print("")
	print("  Attacker:",Battacker.Num,Battacker.name,"with",Battacker.weapon.name)
	print("    Average Score:",D(avScoreAt))
	print("    Average Effective Damage inflicted:",D(avDamageAt))
	print("    Average Total Models lost:",D(avDeathsAt))
	print("")
	print("  Defender:",Bdefender.Num,Bdefender.name,"with",Bdefender.weapon.name)
	print("    Average Score:",D(avScoreDef))
	print("    Average Effective Damage inflicted:",D(avDamageDef))
	print("    Average Total Models lost:",D(avDeathsDef))
	print("")
	print("  Winner:")
	print("    Attacker:",D(avWinAt*100),"%")
	print("    Defender:",D(avWinDef*100),"%")
	print("    Draw:",D(avDraw*100),"%")
	print("")
	print("Execution time: %s seconds " % (time.time() - start_time))
	return


#####

deb=0 # Print debugs or not

#Attacker = Unit.ChaosOgres(10,weapon=Weapon.AHW(AB=1))
Attacker = Unit.StateTroops(5)
#Attacker = Unit.Chosen(2,AddA=1,Sv=4,weapon=Weapon.Halberd())
Defender = Unit.StateTroops(7)
#Defender = Unit.StateTroops(12,AddA=1,Sv=5,weapon=Weapon.Spear())
#Defender = Unit.Greatswords(11,AddA=1)
#Defender = Unit.SkeletonWarriors(20,weapon=Weapon.Spear())

Sim(100000, Attacker, Defender, initiative=2, atBonus=0, defBonus=0, defendedObstacle=1, siegeTower=0)



