<!-- Slide number: 1 -->
# Why phase behavior?
Petroleum reservoir fluids may exist in the reservoirs either as gas, liquid, or gas+liquid
But what determines their state of existence depends on pressure (P) and temperature (T)
Due to P and T reduction, fluids may remain in the original state or change the state as they travel from the reservoir to the surface
In addition to P and T two other parameters that control the state of a given fluid are composition and chemistry
1

<!-- Slide number: 2 -->
# Equilibrium
A condition at which a material appears to be at rest that is not changing in volume or changing phases
For example, a certain P and T at which no more mass transfer takes place between phases
As soon as these conditions change the equilibrium is disrupted, which may result in mass transfer, and the system eventually assumes a new equilibrium condition
Used as a criteria for vapor-liquid flash calculations

2

<!-- Slide number: 3 -->
# Component and composition
Component is a given entity, a constituent, or a pure substance – for e.g., CH4, CO2, N2
Composition is the amount in which a particular component is present in a given mixture or a system based on mass, volume, or mole; the former is the most common in petroleum industry –

![](Picture4.jpg)
the composition of the ith component in a mixture consisting of n number of components; expressed as mole fraction or mole %
3

<!-- Slide number: 4 -->
# Types of physical properties
INTENSIVE and EXTENSIVE
INTENSIVE: Independent of system mass; examples are density, viscosity, composition, pressure, temperature
EXTENSIVE: Dependent of system mass; example volume, flowrate

Most properties of petroleum reservoir fluids are intensive
4

<!-- Slide number: 5 -->
# Phase rule
Pressure, Temperature and Composition variables are denoted as degrees of freedom, F
These degrees of freedom need to fixed so that the conditions of a system or a component at equilibrium may be completely defined
The degrees of freedom (F), Components (C) and Phases (P) are related by the Phase Rule after J. Willard Gibbs (1875) –

F = C – P + 2
5

<!-- Slide number: 6 -->
# Contd.
If:

F = 0, the system is called invariant
F = 1, the system is called univariant
F = 2, the system is called bivariant
F = 3, the system is called trivariant
6

<!-- Slide number: 7 -->
Application of Phase rule
For a single component system, how many degrees of freedom are required so that it exists in single phase –
F = 1 - 1 + 2 = 2
Pressure and temperature must be specified; the system is bivariant
7

<!-- Slide number: 8 -->
Contd.
For a single component system, how many degrees of freedom are required so that it exists in two phase –
F = 1 - 2 + 2 = 1
Either pressure or temperature must be specified; the system is univariant
8

<!-- Slide number: 9 -->
Contd.
For a single component system, how many degrees of freedom are required so that it exists in three phase –
F = 1 - 3 + 2 = 0
The system is invariant; this is a fixed point
9

<!-- Slide number: 10 -->
# Phase behavior of a pure component
Reservoir fluids are basically mixtures of various pure components or single components
Study of phase behavior of pure components helps us in better understanding of key concepts in phase behavior
Pure components such as carbon dioxide also important in reservoir processes; injection of CO2 for EOR purposes (sequestration)
10

<!-- Slide number: 11 -->
# Phase diagram

![](Picture16.jpg)
11

<!-- Slide number: 12 -->

![](Picture4.jpg)
12

<!-- Slide number: 13 -->
# Contd.
The crossing of VP curve in a horizontal (isobaric) or vertical (isothermal) direction signifies the transition from gas to liquid or liquid to gas
The appearance of liquid in any of the above process signifies dew point pressure (at constant temperature) or bubble point temperature (at constant pressure)
The appearance of vapor signifies bubble point pressure or bubble point temperature
For a pure component, at a given temperature of interest –
Pb = Pd = Pvp
13

<!-- Slide number: 14 -->
# Critical point
The upper limit of the VP curve is called the Critical Point
P and T represented by this point are critical pressure (Pc) and critical temperature (Tc); the limiting point at which pure component can form co-existing phases
At critical point the intensive properties of the vapor phase and liquid phase of a pure component are identical
Pure component critical constants are used in EOS modeling

APPLIES ONLY TO A PURE COMPONENT!
14

<!-- Slide number: 15 -->
Normal alkane data
NIST Chemistry webbook is a reliable source for this data. Also,
available as library in all PVT simulators
(https://webbook.nist.gov/chemistry/fluid/ )
15

<!-- Slide number: 16 -->
# Triple point
The lower limit of the VP curve is called the Triple Point
Triple point represents the P and T conditions at which all three phase are in co-existence in equilibrium
CH4 triple point is 90.7K and 0.115 atm
Every single component is invariant at triple point; this is a fixed unique point
16

<!-- Slide number: 17 -->
P-V diagram for n-butane
17

<!-- Slide number: 18 -->
Density-temperature behavior of a pure component
The law of rectilinear diameter
Saturated liquid

Average density

C
Critical density

As T
Liquid density

Density

As T  Vapor density
Saturated vapor
Tc

Temperature

18

<!-- Slide number: 19 -->
Determination of vapor Pressure

Pressure

Temperature
control

Laboratory
determination of –

Vapor pressure
Critical pressure
Critical temperature
Critical volume (volume of the component at
	Pc and Tc) per gm or
	mole of component

Pure
component

Window

Hg

19

<!-- Slide number: 20 -->
Application of corresponding states

![](Picture36.jpg)

![](Picture37.jpg)
Pr

1

Pressure

Temperature
1
Tr
20

<!-- Slide number: 21 -->
Calculation of Vapor Pressure
Lee and Kesler Correlation
w is acentric factor; a constant for every pure component – under supplementary materials there is a PDF containing explanation of w

![](Picture1.jpg)

![](Picture2.jpg)
21

<!-- Slide number: 22 -->

![](Picture1.jpg)
22

<!-- Slide number: 23 -->
Add another component - Binary
Critical point

MIXTURE
PURE

L

P
P
L
L+G
G
G
T
T
23

<!-- Slide number: 24 -->
Phase envelope
Fixed overall composition

![](Picture3.jpg)
24

<!-- Slide number: 25 -->
Bubble Point and Dew Point
For isothermal pressure reduction on
LHS of the critical point
  At pressure A the mixture is liquid until you hit the
   phase boundary or the bubble point curve.
   This intersection is the BUBBLE POINT.

  As you keep depleting the pressure, more gas
   appears.  The further you reduce the pressure
   only a minute amount of liquid remains and the
   dew point curve is crossed.  This is the DEW POINT.

  At point B only gas remains.

  The above DEW POINT is still the normal dew point.
25

<!-- Slide number: 26 -->
The Critical Point
  The definition of critical point applied to single phase
    doesn’t apply.

  In a binary the vapor and liquid can co-exist at
   T & P > critical point.

  The definition of the critical point is simply the point at
   Which the bubble point and dew point line join.

MORE RIGOROUSLY

THE DIFFERENCES BETWEEN
THE VAPOR AND LIQUID PHASES DIMINISH AND
INTENSIVE PROPERTIES OF THE PHASES BECOME
IDENTICAL
26

<!-- Slide number: 27 -->
Cricondentherm & Cricondenbar
    The highest temperature on the
  phase envelope is called the
  CRICONDENTHERM

    The highest pressure on the phase
  envelope is called the
  CRICONDENBAR
27

<!-- Slide number: 28 -->
# Retrograde Condensation
For isothermal pressure reduction on
RHS of the critical point
For continued pressure depletion from point E (mixture is gas phase), small amount of liquid appears when the dew point curve is met – called as retrograde dew point (opposite of the normal behavior)
The retrograde dew point is also known as the upper dew point
With further pressure reduction, mixture passes through the two phase region until it crosses the dew point curve again – this point is the normal or lower dew point
At point F mixture turns into gas phase again
28

<!-- Slide number: 29 -->
# Approaching the Phase Envelope
Beginning with single phase conditions
Isothermal conditions – by altering the pressure – most common as reservoir temperature is assumed constant

Isobaric conditions – by altering the    temperature – not very common but sometimes used in laboratories for studying the phase behavior of mixtures composed of light components because cricondentherm is limiting

29

<!-- Slide number: 30 -->
Effect of system composition
on phase envelopes
CH4+nC4H10 binaries
30

<!-- Slide number: 31 -->
Critical loci of various CH4 and n-paraffin binary mixtures

![](Picture2.jpg)
A larger difference in
molecular size of the components causes the mixtures to have very large
critical pressures, McCain (1990).
31
Brown et. al. (1947)

<!-- Slide number: 32 -->
Application of Phase rule
For a binary system, how many degrees of freedom are required so that it exists in single phase –
F = 2 - 1 + 2 = 3
Pressure, temperature and composition must be specified (fixing one of the components composition fixes the other)
For the binary to exist in two phase; F = 2, i.e., P and T must be specified
32

<!-- Slide number: 33 -->
# Example of a Methane+Propane System
CH4 = 62 mole %, C3H8 = 38 mole %, T = 33.6 oC
33

<!-- Slide number: 34 -->
# Example of a CO2+nTetradecane System
CO2 = 92.4 mole %, nC14H30 = 7.6 mole %
34

<!-- Slide number: 35 -->
# Multicomponent Mixtures
In general the phase behavior of multicomponent hydrocarbon systems in the liquid – vapor region is quite similar to that of the binary systems

As the system becomes more complex with a greater number of different components, the P & T ranges in which two phases exist increase significantly, or in other words the separation between the bubble-point and dew-point lines becomes greater

However, definitions of critical point, cricondentherm, cricondenbar, etc. is the same as that for binary systems

35

<!-- Slide number: 36 -->
Add another component
to the binary = ternary
36

<!-- Slide number: 37 -->
Phase envelopes of mixtures with different proportions of same HC components
All phase envelopes are unique in nature, i.e., valid for a specific overall composition

Pressure, psia
37
Temperature, oF

<!-- Slide number: 38 -->
Construction of Phase Envelopes
T
P

Sapphire window

Test mixture

Mercury

Pump

![](Picture23.jpg)
Alter P & T and monitor for phase changes or transitions.
Typically 2-3 saturation pressures (bubble or dew) in the vicinity of reservoir temperature are measured and the rest of the envelope constructed using EOS models.
38

<!-- Slide number: 39 -->
# Phase behavior of petroleum reservoir fluids
Reservoir fluids require different approaches by reservoir engineers and production engineers

Fluid type is the deciding factor in many field development plans – production strategy, EOR, design of surface facilities etc.

Fluid type needs to be determined early in the life of a reservoir

Most importantly, the behavior of a reservoir fluid during production is determined by the shape of its phase envelope and the position of its critical point
39

<!-- Slide number: 40 -->
# Summary from model mixtures

![](Picture1041.jpg)
Qualitatively, phase behavior of Petroleum Reservoir Fluids is similar, i.e., Reservoir Gases have relatively small phase envelopes, whereas Reservoir Oils have relatively large phase envelopes.
40

<!-- Slide number: 41 -->
# Reservoir fluid composition
Petroleum reservoir fluids are generally composed of numerous components belonging to diverse chemical species
Lighter and the intermediate components (typically the three non-hydrocarbons if they are present, and methane through hexane) are clearly identified
What remains is the unidentified components, which are usually grouped as a plus fraction, C7+
Location of the critical point with respect to cricondenbar is determined by the component distribution
Fluids deficient in intermediates will have critical point on the right of cricondenbar
41

<!-- Slide number: 42 -->
# Black Oils
They consist of a wide variety of chemical  species including large, heavy, nonvolatile molecules

The phase envelope covers a wide temperature range

The critical point is well up the slope of the phase envelope

42

<!-- Slide number: 43 -->
# Phase Envelope of a Black Oil

(Pres,Tres)
1

2
3

100 % liquid
100 % vapor
Curves inside the
phase envelope are iso-vols
Separator Conditions

43

<!-- Slide number: 44 -->
# McCain’s Black Oil

![](Picture3.jpg)
44
McCain (1990)

<!-- Slide number: 45 -->
# Description of Phase Envelope of a Black Oil
The lines within the phase envelope are quality   lines or iso-vols

The vertical line 123 follows the path within the reservoir or the pressure reduction in the reservoir

Typical separator conditions lie at a much lower temperature and pressure

At Pres within section 12 of the line the oil is undersaturated, i.e., bubble point lower than the reservoir pressure

The word undersaturated means that the oil is capable of dissolving more gas
45

<!-- Slide number: 46 -->
# Contd.
At point 2 the oil is at its bubble point and is called as saturated

On further pressure reduction additional gas appears within the reservoir

The oil is saturated anywhere along line 23

Additional gas appears as the oil moves from the reservoir to the surface, the oil shrinks

The separator conditions lie well within the phase envelope indicating the production of large amount of liquid

46

<!-- Slide number: 47 -->
# Field identification and Lab. Analysis of Black Oils
Characterized as having initial gas-oil (GOR) producing ratios in the order of 2000 scf/STB

Stock tank liquid API gravity less than 45o API, dark color

Oil formation Volume Factor less than 2.0 res bbl/STB

The heptane plus fraction is more than 20 mole %

47

<!-- Slide number: 48 -->
# Volatile Oils
They contain relatively fewer heavy molecules, and more intermediates (ethanes through hexanes) in comparison to black oils

The temperature range covered is somewhat smaller

The critical temperature is much lower than for black oils

48

<!-- Slide number: 49 -->
# Phase Envelope of a Volatile Oil
(Pres,Tres)
1

2

3
Tightly spaced iso-vols
Separator Conditions
49

<!-- Slide number: 50 -->
# McCain’s Volatile Oil

![](Picture3.jpg)
50
McCain (1990)

<!-- Slide number: 51 -->
# Description of Phase Envelope of a Volatile Oil
The quality lines are tighter and closer near the bubble point curve

The vertical line 123 shows the path undertaken by the reservoir during the production

A small reduction in pressure below the bubble-point results in a large amount of gas release

Volatile oils can become as much as 50 % gas in the reservoir at only a few 100 psi below the bubble point

Liquid production is usually very low
51

<!-- Slide number: 52 -->
# Field identification and Lab. Analysis of Volatile Oils
Characterized as having initial gas-oil (GOR) producing ratios in the range of 1750 - 3200 scf/STB

Stock tank liquid API gravity is 40o API or higher, brown color

Oil formation Volume Factor greater than 2.0 res bbl/STB

The heptane plus fraction typically lies between 12.5 - 20 mole %
52

<!-- Slide number: 53 -->
# Transition from a Black Oil to a Volatile Oil
Injection of a LPG rich gas in a black oil
10 mole % injection gas
60 mole % injection gas
53

<!-- Slide number: 54 -->
# Gas Condensates
Also called as Retrograde Gases

The phase envelope covers a wider  pressure range

Gas condensates contain fewer of the heavy hydrocarbons that black oils or volatile oils

The critical point on the phase envelope is represented by low pressure and temperatures
54

<!-- Slide number: 55 -->
# Phase Envelope of a Gas Condensate
(Pres,Tres)
1

2
3

Separator Conditions
55

<!-- Slide number: 56 -->
# McCain’s Gas condensate

![](Picture3.jpg)
56
McCain (1990)

<!-- Slide number: 57 -->
# Description of Phase Envelope of a Gas Condensate
Initially the reservoir fluid is in single-phase vapor in the reservoir at point 1

As reservoir pressure decreases the fluid exhibits a retrograde dew-point, point 2

Further reduction in the pressure causes more liquid to precipitate in the reservoir (usually unrecoverable)

Revaporization of the liquid begins at low pressures

However, the above can only be observed in the laboratory, as such low pressures are never encountered in the reservoir
57

<!-- Slide number: 58 -->
# Field identification and Lab. Analysis of Gas Condensates
Lower limit of gas-oil (GOR) producing ratio is in the range of  3500 scf/STB, the upper limit not so well defined

Stock tank liquid API gravity is 40o – 60 oAPI, lightly colored

GOR’s rapidly increase as production begins and reservoir pressure falls below the dew-point

The heptane plus fraction typically less than 12.5 mole %
58

<!-- Slide number: 59 -->
Liquid drop out from
Gas Condensates

Lean gas condensates

Dew point

59

<!-- Slide number: 60 -->
# Wet Gases
Predominantly smaller molecules

The phase envelope covers a wide pressure and narrow temperature range

The word ‘wet’ does not mean that the gas is wet with water but refers to the hydrocarbon liquid or the condensate

The critical point on the phase envelope is represented by very low pressure and temperatures
60

<!-- Slide number: 61 -->
# Phase Envelope of a Wet Gas

(Pres,Tres)
1

2
Separator Conditions
61

<!-- Slide number: 62 -->
# Description of Phase Envelope of a Wet Gas
A wet gas exists solely as a single-phase vapor in the reservoir

The pressure path 12 in the reservoir does not enter the phase envelope

No liquid is formed in the reservoir

However, separator conditions lie within the phase envelope, resulting in some liquid formation at the surface
62

<!-- Slide number: 63 -->
# Field identification and Lab. Analysis of Wet Gases
Wet gases have very high gas-oil (GOR) producing ratios; greater than 50,000 scf/STB

High API gravity (upto 70) water-white stock-tank liquid

The producing GOR remains constant during the life of a wet gas reservoir

The above happens mainly because of the fact that no phase split occurs in the reservoir and reservoir fluid composition remains constant

May not contain any C7+ fraction
63

<!-- Slide number: 64 -->
# Dry Gases
Primarily methane with some intermediates

The phase envelope is narrow and small in comparison to wet gases

The word ‘dry’ indicates that the gas does not contain any heavy molecules to form liquid or condensate
64

<!-- Slide number: 65 -->
# Phase Envelope of a Dry Gas

(Pres,Tres)
1

2
Separator
Conditions
65

<!-- Slide number: 66 -->
# Description of Phase Envelope of a Dry Gas
A dry gas exists solely as a single-phase vapor in the reservoir as well as the separator or surface conditions

The pressure path 12 in the reservoir does not enter the phase envelope and is well outside the phase envelope

The reservoir temperature is much higher than the cricondentherm
66

<!-- Slide number: 67 -->

Classification of reservoirs based on phase envelopes
Gas Reservoirs (Single Phase)
Gas Condensate Reservoirs (Dew-Point Reservoirs)
Undersaturated Solution-Gas Reservoirs (Bubble-Point Reservoirs)
67

<!-- Slide number: 68 -->
# Producing fluids

![](Picture4.jpg)
68
Curtin University

<!-- Slide number: 69 -->
# Separated fluids

### Chart

| Category |  |  |  |  |  |  |  |
|---|---|---|---|---|---|---|---|69

<!-- Slide number: 70 -->
Gas cap and oil interaction

Gas cap fluid
Pbubble = Pdew = Pres.
Pressure
Reservoir oil
Pres.

Tres.
Temperature
70

<!-- Slide number: 71 -->
# Production trends

![](Picture5.jpg)
See September 1994, JPT pages 746-750, McCain
71

<!-- Slide number: 72 -->
Vapor-Liquid Density data for a
North Sea Gas Condensate
Data at 140 oC
72

<!-- Slide number: 73 -->
Vapor-Liquid Density data for a
North Sea Black oil
Data at 100 oC
73

<!-- Slide number: 74 -->
Classification of petroleum reservoir fluids based on field data and laboratory analysis
| Reservoir Fluid | Prod. GOR, scf/STB | API gravity of liquid | Color of stock tank liquid | Mole % of C7+ | Phase split in reservoir | Formation volume factor res. bbl/STB |
| --- | --- | --- | --- | --- | --- | --- |
| Black oil | 250-1750 | 40.0-45.0 | Dark | > 20.0 | Bubble point | < 2.0 |
| Volatile oil | 1750-3200 | > 40.0 | Colored | 12.5-20.0 | Bubble point | > 2.0 |
| Gas condensate | > 3200 | 40.0-60.0 | Lightly colored | < 12.5 | Dew point | Bwg |
| Wet gas | > 50,000 | Upto 70.0 | Water white | May be present in trace amounts | Tres.>cricon. | Bwg |
| Dry gas | No cond. | No cond. | No cond. | - | Tres.>cricon. | Only Bg |
74

<!-- Slide number: 75 -->
SAMPLING OF PETROLEUM
RESERVOIR FLUIDS
75

<!-- Slide number: 76 -->
# Who does what in sampling?
Samples usually collected by field or laboratory technicians (Service Companies)

Other professionals should be familiar with sampling techniques – to a level that accuracy and reliability of the entire procedure can be verified

The engineer needs to decide when a sample is required, what sampling techniques should be used, and how the well should be prepared for sampling
76

<!-- Slide number: 77 -->
# Practical considerations
Sampling may occur at various stages in the life of a reservoir, i.e., exploration or production
However, emphasis should be on early sample collection in the life of a reservoir
If reservoir pressure falls below the saturation pressure – the composition of the original reservoir fluid changes, and with further decline in pressure compositional changes are continuous – especially critical in gas condensate reservoirs
77

<!-- Slide number: 78 -->
# Well conditioning
Even when samples are collected early – well should be conditioned for collection of representative fluid samples
Most important aspect is flowing the well at a reduced flow rate to lower the pressure draw-down
Pressure draw-down is unavoidable in saturated reservoirs - lowest possible stable rate should be used
78

<!-- Slide number: 79 -->

![](Picture2.jpg)
Undersaturated reservoir
79

<!-- Slide number: 80 -->

![](Picture2.jpg)

Saturated reservoir
80

<!-- Slide number: 81 -->
# Limited condensation within a small zone around the wellbore

Gas condensates
Condensate ring build-up;
2 phase region

Pressure decreasing
Pressure decreasing
81

<!-- Slide number: 82 -->
# Methods of Sampling
Surface sampling
Wellhead sampling

Sub-surface sampling (also known as bottom-hole sampling)
82

<!-- Slide number: 83 -->
# Surface Sampling
Consists of taking a given number of gas and liquid samples from the test separator
The flow in the metering period must be preceded by a cleaning period and flow sufficient to remove any drilling and completion fluids
The BHP must remain higher than the fluid saturation pressure.  Since the saturation pressure is unknown at this stage, estimating methods based on the observed GOR are used
As a general rule the minimum flow giving rise to stable conditions is sought
83

<!-- Slide number: 84 -->
# Contd.
One of the major sources of error in this mode of sampling is the liquid carryover in gas samples

In the presence of carryover of liquid into the gas, leading to error in the composition of the recombined fluid

The well should be flowed for a period of time sufficient to stabilize the producing gas-oil ratio at the surface
There are various API standards for sampling
84

<!-- Slide number: 85 -->
# Contd.
The GOR is checked over at least three comparable time intervals – 2hr, 4hr or longer if necessary to obtain the desired stability of the producing GOR
A large quantity of separator gas is collected because of its high compressibility compared with the liquid.
Separator gas is around 5 liters and liquids close to 1 liter, these samples are called as companion samples
Information gathered during the sampling includes – separator T & P, flowing bottom-hole pressure and temperature, and other formation details
The collected samples are physically recombined in the PVT laboratory to obtain the reservoir fluid sample
85

<!-- Slide number: 86 -->

![](Picture2.jpg)
86

<!-- Slide number: 87 -->

![](Picture2.jpg)

87

<!-- Slide number: 88 -->
Basic recombination equation
To determine the compositions of the recombined fluid accurately,
all the phases including the carryover must be considered.
Number of moles	Composition		Phases		Stream

         ng			y	                                   sep. gas

         nl				x		                       sep. liq

equil. gas

equilb. liq.
Feed or wellstream moles =
Moles of vapor + Moles of liquid
88

<!-- Slide number: 89 -->
# Wellhead Sampling
Wellhead sampling is only possible for fluids which are single phase under wellhead conditions

Whenever possible, this is the best and most economic method of sampling

For oils, experience has shown that valid wellhead samples may be obtained, when the wellhead flowing pressure is more than 300 psi above the bubble point of the fluid at wellhead temperature

Effective application of wellhead sampling requires some a priori information on the saturation curve for the fluid because the fluid is going to experience a gradual reduction in the temperature as it travels from reservoir to surface (PT envelope)
89

<!-- Slide number: 90 -->
# Sub-surface or Bottom-hole Sampling
Bottom hole samples of reservoir fluids can be captured using different techniques during well test, drill stem test or using wireline formation tester (WFT)

Wells should be producing with stabilized GOR

At least two fluid samples are collected and checked against each other

Sample volumes are typically 500 to 600 cc
90

<!-- Slide number: 91 -->
Subsurface Single phase
Reservoir Samplers (SRS)

![](Picture3.jpg)

![](Picture2.jpg)
91

<!-- Slide number: 92 -->
# Sampling sheet

![](Picture4.jpg)
92

<!-- Slide number: 93 -->
How to Check the Sample (Non)Representativity
Validity tests or quality checks of separator gas and liquid samples

Measuring the opening pressure of the separator gas bottle and comparing it with separator conditions

Measuring the saturation pressure of the separator liquid sample and comparing it with separator conditions
93

<!-- Slide number: 94 -->
# Contd.
The opening pressure of the separator gas bottle and saturation pressure of the separator liquid should be equal to the separator pressure at separator temperature
Bubble point of the bottom-hole sample at surface temperature less than the sampling pressure

94

<!-- Slide number: 95 -->
Separator sample validity checks

![](Picture3.jpg)

95

<!-- Slide number: 96 -->
Relationship Between the Phase Envelopes of Separator Gas and Oil

Feed

Sep. gas
Pressure

Sep. oil
Psep.

Tsep.
Temperature
96

<!-- Slide number: 97 -->
BHS validity checks

![](Picture3.jpg)

Pbubble < Psampling
97

<!-- Slide number: 98 -->
# Factors affecting sample representativity
Mainly related to the sampling procedures

Mishandling of separator gas and liquid samples if sub-samples are drawn between different stages of the laboratory analyses

Concerned with the presence of solid deposits in the test installation – tubing or separator

Waxes and asphaltene deposition depending on the T& P conditions and the composition of the phase where they are located
98

<!-- Slide number: 99 -->
# Contd.
Sometimes these are precipitated at certain points in the installation and there is a risk that they will not be sampled quantitatively

Unfortunately, the effect of these solid organic constituents on the phase behavior of the reconstituted reservoir fluid is considerable.  Extreme caution is thus needed when sampling such fluids.

Contamination of Reservoir Fluids with Oil-based Mud: significant changes in liquid drop out behavior even with 15% contamination
99

<!-- Slide number: 100 -->
# Identifying contamination
OBM contamination will show up
as spikes in the plot of Carbon
number vs. log of mole %

![](Picture3.jpg)

Approximately a straight line of this graph is actually
the basis of the Pedersen characterization method
100
Pedersen et al. (2015)

<!-- Slide number: 101 -->
# Numerical Cleaning Procedure Used for Contaminated Reservoir Fluid
Essentially uses mass, molar, volume balance

The OBM is typically paraffinic while the pseudo components/fractions are a mix of PNA

Numerical cleaning needs to be done for mole% as well as for correcting the densities

![](Picture6.jpg)
101
Pedersen et al. (2015)

<!-- Slide number: 102 -->
COMPOSITIONAL ANALYSIS OF PETROLEUM
RESERVOIR FLUIDS
102

<!-- Slide number: 103 -->
# Objectives
The physically collected reservoir fluid samples are the starting point for any PVT and phase behavior lab studies on reservoir fluids
Similarly, compositional analysis is the starting point for any modeling study that involves equations of state (EOS)
103

<!-- Slide number: 104 -->
# Contd.
Reservoir fluid composition is the most important input to an EOS model as all calculations are based on this information
Composition of a given reservoir fluid is considered as its signature
Ordinarily, compositional analysis is part of the PVT and phase behavior laboratory analysis

104

<!-- Slide number: 105 -->
# Characteristics of reservoir fluid composition

![](Picture8.jpg)

![](Picture13.jpg)

![](Picture14.jpg)

![oil](Picture11.jpg)

![oil](Picture6.jpg)
Basically split into three different parts:
The well defined components
The pseudo fractions
The plus fraction or the residue
105
ConocoPhillips

<!-- Slide number: 106 -->
# Contd.
Well defined components – are all non-hydrocarbons and methane through n-pentane; all are identified
Pseudo fractions (Single Carbon Number, SCN) – these are represented by a certain carbon number such as C10 or C12 or C15 each containing several paraffins, naphthenes, aromatics
The plus fraction or residue – all unidentified components are lumped in this fraction since it is impossible to identify each one of them, for e.g., C20+ or C30+
106

<!-- Slide number: 107 -->
Characteristics of Reservoir Fluid Composition
Well defined
Pseudo or SCN
Plus or residue
Middle Eastern Black Oil
107

<!-- Slide number: 108 -->
Strategy for compositional analysis
Gas Composition

Oil Composition

Gas
Composition

First stage
separator

Oil
Composition

Second stage
separator
Feed (from wellhead)
108

<!-- Slide number: 109 -->
# Recombination Calculations
After individual compositional analysis of the various streams; the GOR’s are converted to a molar basis
A basis of 1 stock tank barrel of stock tank liquid is used
The idea is to convert all the streams on either a molar or mass basis so that they can be added
The various streams are numerically (for EOS modeling, compositional simulation etc.) as well as physically (for laboratory PVT and phase behavior studies) recombined
109

<!-- Slide number: 110 -->
Numerical recombination
of a black oil
110

<!-- Slide number: 111 -->
# Other compositional methods
Blowdown method applied to BHS or physically recombined separator samples
The physically recombined sample is flashed at atmospheric pressure forming two phases, gas and liquid (requires large sample volumes)
The flashed phases are analyzed compositionally (by gas chromatography or distillation) and are recombined on the basis of the separation ratio
Method works well for low GOR samples, errors could be large in case of condensates or especially lean gas condensates where the condensate formed is rather low
111

<!-- Slide number: 112 -->
# Direct determination of composition
The actual reservoir fluid sample is created by physically recombining the separator products in a PVT cell or the reconditioned BHS sample is loaded in a PVT cell
The reservoir fluid is directly analyzed for compositions by gas chromatography using advanced sampling techniques – the process does not involve any flash
A very small amount of sample is captured from a flow loop, which is part of the PVT cell, and is directly transferred to a gas chromatograph for compositional analysis
The method is particularly advantageous in the determination of fluid compositions in the two phase region when pressure falls below the saturation pressure
112

<!-- Slide number: 113 -->
Contd.

![](Picture1026.jpg)

113

<!-- Slide number: 114 -->
Mass/Mole balance for direct
determination of compositions
114

![](Picture6.jpg)

<!-- Slide number: 115 -->
# Contd.
Measure composition of the single phase fluid
Equilibrium vapor and liquid phase compositions and densities are measured at various pressures below the saturation pressure
The measured compositions, densities and volumes are used in mass/mole balance to calculate the single phase composition at various pressure stages
115

<!-- Slide number: 116 -->
Mass/Mole balance equations

![](Picture5.jpg)

![](Picture6.jpg)
116

<!-- Slide number: 117 -->
# Gas Chromatography
Traditionally, compositional data in petroleum industry have only been reported upto C7+, the compositional information being mainly based on low temperature fractional distillation data

This level is inadequate for accurate modeling of the phase equilibrium and physical properties of the petroleum reservoir fluids

In recent years, new techniques have been developed for experimentally determining the composition of petroleum reservoir fluids.  These methods yield a far more accurate and detailed description of the petroleum reservoir fluids.
117

<!-- Slide number: 118 -->
# Gas Chromatography

![](Picture4.jpg)

118

<!-- Slide number: 119 -->
# Essential components of a GC
Porous, packed column
Detectors
TCD (Thermal Conductivity Detector) for analysis of non hydrocarbon components
FID (Flame Ionization Detector) for analysis of hydrocarbon components
Temperature programmed oven
Carrier gas
Injection valve/sampling valve
Splitters

119

<!-- Slide number: 120 -->
# A typical gas chromatogram
Component peaks – heights, areas used for quantification

![](Picture4.jpg)

120

<!-- Slide number: 121 -->
# True Boiling Point (TBP) Distillation

![](Picture4.jpg)
121

<!-- Slide number: 122 -->
# Contd.
Flashed liquid sample volumes close to 100 ml

TBP cuts at specified temperature intervals; C9 cut means the fraction collected between 0.5 oC above the boiling point of nC8 and 0.5 oC above the boiling point of nC9

Atmospheric pressure used from C6 cut to C10

Vacuum of 20 mm Hg used for cuts from C10 to C20+ to avoid thermal cracking of the sample and reduce heat requirements, can be extended upto C30+ with vacuum of the order of 2 mmHg

Average physical properties of TBP fractions or pseudo fractions are measured i.e., density, molecular weight, viscosity, etc.
122

<!-- Slide number: 123 -->
# Advantages of TBP distillation
Produces an actual physical sample of individual pseudo fractions present in the oil sample and the residue

The measured TBP data is also of benefit to the refining industry

Average physical properties of pseudo fractions are employed to determine Tc, Pc, Omega etc. for phase behavior calculations

Viscosity measurements can be used to obtain P-N-A distribution of TBP fractions to improve phase behavior predictions

TBP fractions can be used for creating various fluid samples in PVT laboratories
123

<!-- Slide number: 124 -->
# Density, Molecular Weight and Viscosity
Densities of TBP fractions are generally measured using an Anton-Paar oscillating tube densitometer
Molecular weights of TBP fractions are measured using the freezing point depression technique.  The apparatus is called as ‘Cryette’.
Viscosities can be measured using Rolling Ball type microviscometers
Individual TBP fractions can be analyzed further by GC in order to provide even more detailed composition
124

<!-- Slide number: 125 -->
# Densitometer and Cryette

![](Picture15.jpg)

![](Picture14.jpg)
125

<!-- Slide number: 126 -->
# Rolling Ball Microviscometer

![](Picture6.jpg)
Measurement of wide range of viscosities; sample volume required is very small – suitable for TBP fractions as the volumes are small
126

<!-- Slide number: 127 -->
# Typical TBP Distillation Data
North Sea Oil
127

<!-- Slide number: 128 -->
Internal Consistency of TBP Data
Sample mass charged should match the summation of masses of individual TBP fractions

128

<!-- Slide number: 129 -->
Contd.
Calculated average molecular weight from the data of individual fractions should match the molecular weight of the sample charged

![](Picture3.jpg)
129

<!-- Slide number: 130 -->
Contd.
Calculated average density from the data of individual fractions should match the density of the sample charged

![](Picture6.jpg)
130

<!-- Slide number: 131 -->
Generalized pseudo fractions or SCN data

![](Picture5.jpg)

131

<!-- Slide number: 132 -->
Contd.

![](Picture2.jpg)
Under supplementary materials on Canvas there is a excel file that contains this database

![](Picture1.jpg)

![](Picture2.jpg)
Ahmed
132

<!-- Slide number: 133 -->
Generalized correlation of generalized properties of SCN

![](Picture5.jpg)
q = any physical property
n = number of carbon atoms, 6-45

![](Picture2.jpg)
133
Ahmed

<!-- Slide number: 134 -->
# Watson Characterization Factor
Used to indicate paraffinicity, aromaticity of the fractions or the
overall crude

Assuming a constant value of K, sometimes it is used to
calculate MW or SG instead; if either is known
134

<!-- Slide number: 135 -->
Molar Distribution
of TBP Fractions
Basis for Pedersen characterization method
North Sea Oils
135

<!-- Slide number: 136 -->
# Specific gravity distribution of TBP Fractions
North Sea Oils
136

<!-- Slide number: 137 -->
Molecular weight distribution
of TBP Fractions
137

<!-- Slide number: 138 -->
Variation in PNA distribution
of TBP fractions
Two different gas condensates from North Sea
138
Pedersen

<!-- Slide number: 139 -->
Use of sp. gravity and molecular
weight data of TBP cuts
Under supplementary materials on Canvas. Also, all PVT simulators have various correlation options available

![](Picture2.jpg)

![](Picture10.jpg)
q = Tc, Pc, Vc, Tb (Riazi and Daubert)
q = a(MW)b gc EXP[d(MW) + eg + f(MW)g]
Acentric factor, w (Edmister)

![](Picture3.jpg)
139

<!-- Slide number: 140 -->
# Effect of Pseudo and plus Fraction Properties on Phase Behavior Calculations

Always recommended

140

<!-- Slide number: 141 -->
Other non-conventional methods of compositional analysis

Pressure core

Pore fluids are recovered
from the core by thawing, distillation, extraction
and analyzed for composition
141

<!-- Slide number: 142 -->
Typical compositional data
142
Pedersen

<!-- Slide number: 143 -->
Variation in C7+ properties
Even within the same fluid type
143
Pedersen

<!-- Slide number: 144 -->
Characterization of pseudo fractions and plus fractions (residue)
144

<!-- Slide number: 145 -->
# Significance of fluid characterization

This is the main problem!
Small C7+ in condensate but
significant problem is EOS modeling

145

<!-- Slide number: 146 -->
# Contd.
The primary objective is to extend the compositional description of a given reservoir fluid for improved prediction of phase behavior and fluid properties
146

<!-- Slide number: 147 -->
# How is splitting accomplished?
Experimental: True boiling point distillation of the flashed oil or dead oil – this is typically representative of the C6+/C7+ fraction
Use the distilled cuts to measure their physical properties such as MW and SG
MW and SG is used in various empirical correlations to obtain Tc, Pc, w
End result: compositional distribution from C6+/C7+ to perhaps Cxx+, physical properties and the required EOS data
Subsequently, fractions can be lumped to address the time consuming reservoir simulation issue
147

<!-- Slide number: 148 -->
# Practical example – limited data (some nuances to consider)
Only data available is the API gravity. For e.g., Bartlett oil 16.8 deg API
Assuming that this API gravity represents C6+. How do we proceed?
16.8 deg API means C6+ =  0.9541
Now we need to obtain C7+ and MWC7+. Use some empirical correlations and apply molar balance equations.
148

<!-- Slide number: 149 -->
# C7+ and API empirical correlation

![](Picture5.jpg)
My unpublished correlation
149

<!-- Slide number: 150 -->
# C7+ and MWC7+ empirical correlation

![](Picture2.jpg)
My unpublished correlation
150

<!-- Slide number: 151 -->
# Balance equations
151

<!-- Slide number: 152 -->
# Splitting concept

152

<!-- Slide number: 153 -->
# Splitting requirements/criteria

153

<!-- Slide number: 154 -->
# Contd.

![](Picture35.jpg)
154

<!-- Slide number: 155 -->
# Splitting schemes
Katz method
Lohrenz method
Pedersen method
Whitson method
155

<!-- Slide number: 156 -->
# Katz method
In 1983, Katz presented a simple correlation for breaking down the C7+ fraction into pseudo components – useful for condensate systems
Zn = 1.38205 Z7+e–0.25903n
156

<!-- Slide number: 157 -->
# Application of Katz method
| Component | Mole fraction |
| --- | --- |
| N2 | 0.0060 |
| CO2 | 0.0334 |
| C1 | 0.7416 |
| C2 | 0.0790 |
| C3 | 0.0415 |
| iC4 | 0.0071 |
| nC4 | 0.0144 |
| iC5 | 0.0053 |
| nC5 | 0.0066 |
| C6 | 0.0081 |
| C7+ | 0.0569 |
C7+ properties:
MW = 151.06
Specific gravity = 0.8085
Using n = 7, 8, 9…
Zn values are calculated and
molar composition of C7+
is extended
157

<!-- Slide number: 158 -->
# Contd.
C20+

158

<!-- Slide number: 159 -->
# Contd.
Molar composition is extended
Still need to determine the molecular weight and the specific gravity of the pseudo fractions and especially the plus fraction
Pseudo fractions 7 to 19 MW and SG are from the generalized values of Katz and Firoozabadi
C20+ fraction molecular weight and specific gravity is determined from balance equations
MWC20+

159

<!-- Slide number: 160 -->
# Katz example results
| Component | Mole fraction | MW | g |
| --- | --- | --- | --- |
| C7 | 0.0128 | 96 | 0.722 |
| C8 | 0.0099 | 107 | 0.745 |
| C9 | 0.0076 | 121 | 0.764 |
| C10 | 0.0059 | 134 | 0.778 |
| C11 | 0.0046 | 147 | 0.789 |
| C12 | 0.0035 | 161 | 0.800 |
| C13 | 0.0027 | 175 | 0.811 |
| C14 | 0.0021 | 190 | 0.822 |
| C15 | 0.0016 | 206 | 0.832 |
| C16 | 0.0012 | 222 | 0.839 |
| C17 | 0.0010 | 237 | 0.847 |
| C18 | 0.0007 | 251 | 0.852 |
| C19 | 0.0006 | 263 | 0.857 |
| C20+ | 0.0026 | 499 | 1.038 |
160

<!-- Slide number: 161 -->
# Lohrenz method
Lohrenz (LBC viscosity correlation) presented a method of splitting the C7+ based on partial molar distribution of C7+

Zn = Z6eA(n-6)2+ B(n-6)
161

<!-- Slide number: 162 -->
# Application of Lohrenz method
| Component | Mole fraction |
| --- | --- |
| C1 | 0.9135 |
| C2 | 0.0403 |
| C3 | 0.0153 |
| iC4 | 0.0039 |
| nC4 | 0.0043 |
| iC5 | 0.0015 |
| nC5 | 0.0019 |
| C6 | 0.0039 |
| C7 | 0.00361 |
| C8 | 0.00285 |
| C9 | 0.00222 |
| C10 | 0.00158 |
| C11+ | 0.00514 |
Using experimental partial molar
distribution from C6 to C10,
determine
A = – 0.0401
&
B = – 0.0665
Using fitted A and B
determine mole fractions
of C11 through C15; mole
fraction, MW and
SG of C16+ calculated
from balance equations
C7+ DATA:
MW = 141.25
SG = 0.797
Plus fraction can go to
even higher carbon numbers
162

<!-- Slide number: 163 -->
# Pedersen method
Method based on general molar distribution of C7+

C7

ln (Zn) = A + BCn
163

<!-- Slide number: 164 -->
# Contd.
ln (Zn) = A + BCn
Above equation can also be expressed in terms of molecular weights instead as suggested by Danesh:

MWn = 14n – d
d depends on the chemical nature of SCN; a value of 4 is suggested as an approximation
MWn = 14n – 4
ln (Zn) = A + BMWn
IF TBP data is available upto C20+ then C7 to C19 data can be used to determine A and B and split the C20+ even further

164

<!-- Slide number: 165 -->
# Application of Pedersen method
Same data used in earlier example of Lohrenz method
A and B of Pedersen Method

165

<!-- Slide number: 166 -->
# Contd.
Using fitted A and B
determine mole fractions
of C11 through C15; mole
fraction, MW and
SG of C16+ calculated
from balance equations
Plus fraction can go to
even higher carbon numbers
166

<!-- Slide number: 167 -->
# Splitting of the C7+ Fraction Using Different Methods
167

<!-- Slide number: 168 -->
# Calculated MW and SG of the C16+  fraction Using Different Methods
168

<!-- Slide number: 169 -->
# Pedersen method for limited data
The constants A and B in the Pedersen method can also be obtained when little or no compositional data of the C7+ fraction is available
The values of A and B can be obtained merely on the basis of mole fraction of C7+, its molecular weight and specific gravity by solving two material balance equations
After obtaining A and B the C7+ can be split into the desired number of SCN fractions and a heavier plus fraction such as C20+ or C30+
169

<!-- Slide number: 170 -->
# Contd.
ln (Zn) = A + BMWn

![](Picture5.jpg)

![](Picture6.jpg)

ZC7+, MC7+ are mole fraction and molecular weight of C7+
ZCn and MCn are molecular weights of SCN
N represents the heaviest carbon number assumed to be present in the mixture, for example 40 or 50
170

<!-- Slide number: 171 -->
# Example
The mole fraction, molecular weight and specific gravity of a C7+ fraction of a gas condensate sample are 0.0392, 165 and 0.815 respectively.  Describe the fraction by SCN groups extended to C20+

![](Picture4.jpg)

![](Picture5.jpg)

![](Picture6.jpg)
171

<!-- Slide number: 172 -->
# Example contd.

![](Picture4.jpg)

![](Picture8.jpg)

![](Picture6.jpg)

![](Picture16.jpg)

Assume the highest carbon number to be 45 (N)
Use the generalized molecular weights for 7 through 45
MC7+ is given
Determine B such that the summation is zero; B value for this example comes to -0.0131418
172

<!-- Slide number: 173 -->
# Example contd.

![](Picture4.jpg)

A is directly calculated, which comes to -3.8098
Based on A and B all ZCn values are calculated for carbon numbers from 7 through 45
Summation of mole fractions of C20 through C45 is the C20+ mole fraction
Molecular weight and specific gravity of the C20+ fraction are determined from the balance equations
173

<!-- Slide number: 174 -->
# Example contd.

![](Picture4.jpg)

![](Picture6.jpg)

![](Picture7.jpg)
174

<!-- Slide number: 175 -->
# Whitson method
Whitson proposed a somewhat complicated method to characterize the plus fraction
Zuo and Zhang (2000), SPE 64520, compared both characterization methods for various different fluids, i.e., Pedersen’s exponential as well as Whitson’s probability density function and came to the conclusion that the characterization method of Pedersen et al. usually gives better predictions than that of Whitson.
175

<!-- Slide number: 176 -->
# Heavy oils

![](Picture3.jpg)
18oAPI

C11
Typical oils

![](Picture2.jpg)
C7
28oAPI

![](Picture4.jpg)
10oAPI
C17

For heavy oils or API of the order of 10, partial molar distribution upto C20+ must be available to further characterize the fluid
176
Pedersen et al., 2015

<!-- Slide number: 177 -->
# Splitting method drawbacks
Significant variation in the calculated molecular weight and specific gravities of the extended plus fraction
The variation will result in significantly different critical properties and acentric factors of the plus fraction – uncertainty in EOS predictions
Unfortunately, calculated MW and SG of the extended plus fraction may be unrealistic due to measurement errors in the C7+ MW, split compositions, approximate nature of generalized MW and SG
Sometimes the MW and SG of C7+ is adjusted within certain error bands (experimental uncertainties) to obtain a reasonable value of MW and SG of extended plus fraction
177

<!-- Slide number: 178 -->
# Determination of Tc, Pc and w of split fractions
Pseudo fraction properties can be taken from the generalized values of Katz and Firoozabadi or can be determined from other correlations that use MW and SG
Extended plus fraction properties can be obtained from Riazi and Daubert correlations and Edmister correlation (w) or other empirical correlations
178

<!-- Slide number: 179 -->
# Tc, Pc and w correlations
Correlations for C7+ (Rowe)
(Tc) C7+ = 1.8[961 – 10a]

in oR

![](Picture7.jpg)
in psia

![](Picture12.jpg)
in oR

![](Picture9.jpg)

![](Picture10.jpg)

![](Picture11.jpg)
179

<!-- Slide number: 180 -->
Correlations for C7+ (Standing)

![](Picture4.jpg)

![](Picture5.jpg)
In addition to these two correlations, Riazi & Dauberts
expressions can also be used

180

<!-- Slide number: 181 -->
# Cavett’s correlation for SCN fractions

![](Picture5.jpg)

![](Picture6.jpg)

![](Picture7.jpg)
181

<!-- Slide number: 182 -->
# Cavett’s correlation coefficients

![](Picture4.jpg)
182

<!-- Slide number: 183 -->
# Kesler-Lee correlations for SCN fractions

![](Picture4.jpg)

![](Picture5.jpg)
Pc, Tc, Tb are all in oR
183

<!-- Slide number: 184 -->
# w correlations for SCN fractions

![](Picture4.jpg)

![](Picture5.jpg)

![](Picture8.jpg)

![](Picture7.jpg)

![](Picture10.jpg)

![](Picture9.jpg)

184

<!-- Slide number: 185 -->
# Soereide correlation for boiling point

![](Picture4.jpg)

Tb is in oR
185

<!-- Slide number: 186 -->
# Lumping
On one hand we talk about splitting the plus fraction into several carbon number fractions and on the other hand we talk about lumping them – this may sound like a paradox!  But it is not.
Lumping actually refers to grouping the split carbon number fractions as per certain well defined procedures
Lumping is not carried out randomly
Primary objective of lumping is to reduce the number of components or fractions to minimize the computational time, especially in compositional reservoir simulation type of processes where literally thousands of PT flashes are carried out

186

<!-- Slide number: 187 -->
# Lumping methods
Method developed by Whitson is commonly used
Major challenge associated with lumping schemes is the regrouping of components without losing the EOS prediction accuracy
the basis of selection of components to be grouped for representation by one single component
the assignment of critical properties and acentric factors to the lumped group
187

<!-- Slide number: 188 -->
# Whitson method
Ng = Int[1 + 3.3log(N – n)]

![](Picture7.jpg)
188

<!-- Slide number: 189 -->
# Contd.
 Molecular weight separating each MCN group is given by:
MWI = MWn

![](Picture15.jpg)
189

<!-- Slide number: 190 -->
# Lumping example
Using the Katz method splitting example

![](Picture4.jpg)
20

MWI = 96
MWI = 96[1.333172 ]I
190

<!-- Slide number: 191 -->
# Grouping/Lumping
| Group I | Component | Mole fraction, Zi | MW | ZI |
| --- | --- | --- | --- | --- |
| 1 | C7 | 0.0128 | 96 | 0.0362 |
|  | C8 | 0.0099 | 107 |  |
|  | C9 | 0.0076 | 121 |  |
|  | C10 | 0.0059 | 134 |  |
| 2 | C11 | 0.0046 | 147 | 0.0145 |
|  | C12 | 0.0035 | 161 |  |
|  | C13 | 0.0027 | 175 |  |
|  | C14 | 0.0021 | 190 |  |
|  | C15 | 0.0016 | 206 |  |
| 3 | C16 | 0.0012 | 222 | 0.0035 |
|  | C17 | 0.0010 | 237 |  |
|  | C18 | 0.0007 | 251 |  |
|  | C19 | 0.0006 | 263 |  |
| 4 | C20+ | 0.0026 | 499 | 0.0026 |
| I | MWI |
| --- | --- |
| 1 | 145 |
| 2 | 219 |
| 3 | 330 |
| 4 | 499 |
191

<!-- Slide number: 192 -->
# Tc, Pc, Vc and w of lumped fractions
Normalize the mole fractions first and use simple molar mixing rules proposed by Lee

gL =

MWL =

VcL =

PcL =

TcL =

wL =

192

<!-- Slide number: 193 -->
# Results
| Group I | ZI | MWL | gL | VcL, ft3/lb | PcL, psia | TcL, oR | wL |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.0362 | 110 | 0.7482 | 0.06272 | 412 | 1043 | 0.320 |
| 2 | 0.0145 | 146 | 0.8029 | 0.06304 | 268 | 1074 | 0.407 |
| 3 | 0.0035 | 239 | 0.8473 | 0.06354 | 229 | 1361 | 0.616 |
| 4 | 0.0026 | 499 | 1.0380 | 0.06517 | 112 | 1703 | 0.997 |
Properties for C7 to C19 are Katz and Firoozabadi’s generalized values, whereas properties of C20+ are for a carbon number that has a molecular weight close to 499 (or plus fraction properties can be calculated from empirical correlations)

The lumping method also applies to the fluids where complete TBP distillation data is available upto C20+ or C30+
193

<!-- Slide number: 194 -->
# Composition retrieval or delumping
When flash calculations are carried out using a lumped reservoir fluid, the calculated equilibrium vapor and liquid phase compositions will be in terms of the grouped or lumped components
This information may not be adequate in some processes such as miscible gas injection, gas cycling or compositionally sensitive processes
Composition retrieval or delumping basically means the determination of the distribution of individual components in the equilibrium phases from the distribution of the lumped group in equilibrium phases
For example, a lumped group G is made up of SCN C7 through C10.  In a flash calculation this lumped group results in a composition XG and YG; the objective then is to find out the compositional distribution in terms of XC7, XC8, XC9, XC10 and same for the Y
194

<!-- Slide number: 195 -->
# Equilibrium ratios in a MBC study with methane

![](Picture4.jpg)
Data from Danesh
195

<!-- Slide number: 196 -->
# Contd.
A black oil was vaporized repeatedly by methane at 100oC and 5000 psig
Obviously after each contact the original composition of the oil changes
This also results in the variation of equilibrium ratios for each component due to changes in the mixture composition
This variation can be expressed in terms of a linear function such as:
196

<!-- Slide number: 197 -->
# Procedure for retrieval
Equilibrium ratios of the groups obtained by flash calculations are employed to determine the constants Co and C1
The determined constants are then used to calculate the equilibrium ratios of the original components
Molar balance equations are then used to retrieve the full description of both phases
The detailed mixture composition in the equilibrium phases can then be used in further applications
197

<!-- Slide number: 198 -->
# Delumping example
A reservoir oil is described by the following feed composition and groups
This oil is flashed at 100oC and a certain pressure that results in equilibrium vapor and liquid that has the following composition
The Ki values are calculated from the equilibrium compositions
The objective is to calculate the composition of the equilibrated phases in terms of the original components

![](Picture4.jpg)
198

<!-- Slide number: 199 -->
# Example contd.

![](Picture4.jpg)
Ln(K)
199

<!-- Slide number: 200 -->
# Example contd.
Molar balance equations for one mole of feed:
Zi = Xi(nL) + Yi(nV)

nL = 0.56239 and Ki = Yi/Xi

Zi = 0.56239Xi + 0.43761KiXi

200

<!-- Slide number: 201 -->
# Delumped compositions

![](Picture4.jpg)
For e.g.,, for n-C4
Ln(Ki) = -0.3342+2.5341*(-0.16771)
Ki = 0.46807
For e.g.,, for n-C4
Xi = Zi (FEED – GIVEN)/(0.56239+0.43761*0.46807)

201

<!-- Slide number: 202 -->
# Comparison
202

<!-- Slide number: 203 -->
Laboratory PVT tests of Petroleum Reservoir Fluids
203

### Notes:

<!-- Slide number: 204 -->
# Background
Almost all hydrocarbon fluids are produced by pressure depletion at a constant reservoir temperature
Depleting pressure causes change of phase and fluid property variation
The qualitative and quantitative changes in fluid phase behavior and properties is essential for overall reservoir management
Experimental PVT and reservoir fluid properties studies that attempt to simulate the reservoir depletion process is the best source of obtaining fluid data for reservoir management
204

### Notes:

<!-- Slide number: 205 -->
Reservoir Fluid Studies
Reservoir Fluid Sample

PVT Equipment

Laboratory PVT tests

Reservoir Fluid Properties
205

### Notes:

<!-- Slide number: 206 -->
# Introduction to properties of petroleum reservoir fluids
Properties primarily include the Pressure-Volume (PV) relationships for various fluids at isothermal conditions
Specific properties include compressibility, expansivity, density, viscosity, surface tension, and reservoir engineering parameters such as formation volume factors and solution gas-oil ratios
206

### Notes:

<!-- Slide number: 207 -->
# PV relationship*
All ideal gases obey the relationship –

				PV = nRT

P = pressure		V = volume
 n = no. of moles	R = universal gas const.
 T = temperature

![](Picture4.jpg)
R =
*	Applicable at relatively high temperatures
	and low pressures
207

### Notes:

<!-- Slide number: 208 -->
# Standard Volume
Also known as volume at base conditions or standard conditions – atmospheric pressure and 60oF
Important in gas sales, recombination calculations, and other fluid property calculations
Vsc:

![](Picture5.jpg)
208

### Notes:

<!-- Slide number: 209 -->
# PV relationship – real gases
Gases display Real Gas (Non Ideal Gas) behavior at high pressures and low temperatures; PVnRT
To express a more exact relationship between P, V & T a correction factor called as compressibility factor, gas deviation factor, or simply the Z factor is introduced to account for the departure from ideality:

![](Picture4.jpg)
PV = ZnRT;       Z =PV/nRT =
Z = f(P, T, gas composition)
209

### Notes:

<!-- Slide number: 210 -->
Z factor of pure gases

![](Picture6.jpg)

Z  0.88

Methane,
NGPA
210

### Notes:

<!-- Slide number: 211 -->

![](Picture3.jpg)
Z  0.88

Ethane,
NGPA
211

### Notes:

<!-- Slide number: 212 -->

![](Picture4.jpg)

Z  0.88

Propane,
NGPA
212

### Notes:

<!-- Slide number: 213 -->
Application of corresponding
states for determination of Z factor
Determine the compressibility factors from individual charts:

Methane at P = 1335.6 psia and T = 549.4oR
Ethane at P = 1415.6 psia and T = 880.2oR
Propane at P = 1232.6 psia and T = 1065.6oR

Using Pc and Tc for methane, ethane and propane: Pr = 2 and Tr = 1.6

If P and T are expressed in reduced quantities, Z factor can be generalized
213

### Notes:

<!-- Slide number: 214 -->
Generalized compressibility factor for pure components
214

### Notes:

<!-- Slide number: 215 -->
# Gas density and specific gravity

![](Picture6.jpg)

![](Picture9.jpg)
MWair = 28.97
215

### Notes:

<!-- Slide number: 216 -->
# Critical properties of gas mixtures
If generalized charts for Z factor are to be used – critical properties of gas mixtures are required for calculating the reduced P and T
Pc and Tc for gas mixtures are calculated on the basis of mixture compositions; values are denoted as pseudocritical pressure (Ppc) and pseudocritical temperature (Tpc) – because these are not real
216

### Notes:

<!-- Slide number: 217 -->
# Contd.
Simple Kay’s mixing rules (used extensively in other calculations also) –

Other empirical methods that use gas gravity to determine Ppc and Tpc
Methods that include the correction for presence of non-hydrocarbons, and high molecular weight gases

![](Picture5.jpg)
Ppc =

![](Picture6.jpg)
Tpc =
217

### Notes:

<!-- Slide number: 218 -->
# Ppr and Tpr example problem
| Component | Mole fraction, Yi |
| --- | --- |
| N2 | 0.05 |
| CO2 | 0.05 |
| H2S | 0.02 |
| C1 | 0.80 |
| C2 | 0.05 |
| C3 | 0.03 |
|  | 1.00 |
at 3500 psia and 200oF
218

### Notes:

<!-- Slide number: 219 -->
Uncorrected Ppc and Tpc from Kay’s mixing rules
| Comp | MW | Pc - atm | Tc-K | Ppc | Tpc | MW |
| --- | --- | --- | --- | --- | --- | --- |
| 0.05 | 28.013 | 33.5 | 126.2 | 1.675 | 6.31 | 1.40065 |
| 0.05 | 44.01 | 72.8 | 304.2 | 3.64 | 15.21 | 2.2005 |
| 0.02 | 34.08 | 88.2 | 373.2 | 1.764 | 7.464 | 0.6816 |
| 0.8 | 16.043 | 45.4 | 190.6 | 36.32 | 152.48 | 12.8344 |
| 0.05 | 30.07 | 48.2 | 305.4 | 2.41 | 15.27 | 1.5035 |
| 0.03 | 44.097 | 41.9 | 369.8 | 1.257 | 11.094 | 1.32291 |
|  |  |  |  | 47.066 (691.68 psia) | 207.828 (374.4oR) | 19.94356 |
Calculate corrected Ppc and Tpc from Carr-Kobayashi-Burrows method correction

![](Picture6.jpg)
219

### Notes:

<!-- Slide number: 220 -->

![](Picture254.jpg)
374.4 – (80*0.05) + (130*0.02) – (250*0.05) = 360.05oR

691.68 + (440*0.05) + (600*0.02) – (170*0.05) = 717.18 psia

Tpr = (200+460)/360.05 = 1.83

Ppr = 3500/ 717.18 = 4.88

Make sure both T & P are in absolute units

gg = 19.94356/28.97 = 0.688
220

### Notes:

<!-- Slide number: 221 -->
# Pseudocritical Properties from Gas Gravity

![](Picture1.jpg)

In Sutton’s above correlations PpcHC and TpcHC are the pseudocritical pressure and temperature, respectively and gHC is the gas gravity*
These correlations are in the DAK Excel spreadsheet for calculating the Z factor
Sutton claims that these are the most reliable correlations for calculating pseudocritical properties with the Standing-Katz Z-factor chart. He even claims that this method is superior to the use of composition and mixing rules

221
* Other references list this as Tpch, Ppch and h

### Notes:

<!-- Slide number: 222 -->

![](Picture4.jpg)
Z factor of gas mixtures

NGPA

222

### Notes:

<!-- Slide number: 223 -->
Calculation of
Compressibility Factors
Papay
Hall-Yarborough
Dranchuk-Abu Kassem
Dranchuk-Purvis-Robinson
Hankinson-Thomas-Phillips

![](Picture2.jpg)

![](Picture1.jpg)
223

### Notes:

<!-- Slide number: 224 -->
Dranchuk-Abu Kassem

Z =

![](Picture2.jpg)
rr = reduced gas density; expressed by

![](Picture13.jpg)
rg =
224

### Notes:

<!-- Slide number: 225 -->
# Dry gas formation volume factor
Gas formation volume factor Bg
	[res bbl/SCF] or [ft3/SCF]

Reservoir Conditions
Standard Conditions
Simple to deal with as no phase or
compositional changes occur anywhere
225

### Notes:

<!-- Slide number: 226 -->
Contd.

![](Picture4.jpg)

![](Picture3.jpg)

![](Picture10.jpg)

![](Picture9.jpg)
Bg =
ft3/scf,
bbl/scf

226

### Notes:

<!-- Slide number: 227 -->
Contd.
227

### Notes:

<!-- Slide number: 228 -->
Isothermal compressibility

![](Picture4.jpg)

![](Picture5.jpg)

![](Picture6.jpg)
Ideal gases; Z = 1,
228

### Notes:

<!-- Slide number: 229 -->
Gas viscosity
100oF

150oF

200oF

Viscosity (cp)
T increasing
200oF
150oF
100oF
Pressure
229

### Notes:

<!-- Slide number: 230 -->
# Wet gases
Surface gas composition and reservoir gas composition is different due to condensate formation on the surface
Surface gas properties and reservoir gas properties are different
Based on integration of surface data, composition of reservoir gas or its properties are directly calculated
Mainly two types of integration or recombination cases, i.e.,  compositional data of surface streams is known and the other in which compositional analysis is unavailable
230

### Notes:

<!-- Slide number: 231 -->
Separator compositions
On the basis of YRGi reservoir gas properties can be determined
YSPi

RSP

YSTi

First stage
separator
RST

XSTi
gSTC

YRGi ?
Second stage
separator
Feed (from wellhead)
231

### Notes:

<!-- Slide number: 232 -->
Recombination
basis as 1 stock tank barrel (STB) of condensate

![](Picture4.jpg)
gSTC =

rSTC = 62.43 gSTC lb/ft3
1 STB = (5.615 ft3)  (rSTC lb/ft3) = (5.615 ft3)  62.43 gSTC lb/ft3 = 350.5gSTC lb

![](Picture9.jpg)
MWSTC =
232

### Notes:

<!-- Slide number: 233 -->

1 STB =
 ,

![](Picture8.jpg)

Separator gas
1 lb-mole of gas occupies 379.6 scf
233

### Notes:

<!-- Slide number: 234 -->
Stock tank gas

![](Picture2.jpg)
molar ratio for stock tank condensate

![](Picture6.jpg)
234

### Notes:

<!-- Slide number: 235 -->
Combining all three streams for component i

![](Picture3.jpg)
YSPi

![](Picture4.jpg)
YSTi

![](Picture5.jpg)
XSTi
235

### Notes:

<!-- Slide number: 236 -->
Composition is finally normalized to 1 or 100%

YRGi =

![](Picture3.jpg)
Final equation; once reservoir gas composition is known Z factor and viscosity
can be calculated
236

### Notes:

<!-- Slide number: 237 -->
# Compositions are unknown
Calculations are based on properties of separator gases and GOR’s

Again taking the basis of 1 STB of condensate, mass of reservoir gas, mR is given by –

Weighted average surface gas gravity

![](Picture4.jpg)
gg =
R = RSP + RST

![](Picture9.jpg)

![](Picture10.jpg)
+
237

### Notes:

<!-- Slide number: 238 -->

mR = 0.0763Rgg + 350.5gSTC

![](Picture6.jpg)
Moles of reservoir gas, nR –

![](Picture10.jpg)

![](Picture9.jpg)
+

![](Picture17.jpg)
nR = 0.002634R +
238

### Notes:

<!-- Slide number: 239 -->
Specific gravity of reservoir gas –

![](Picture8.jpg)
ggR =

![](Picture12.jpg)
ggR =

![](Picture18.jpg)
MWSTC =
239

### Notes:

<!-- Slide number: 240 -->
# Wet gas formation volume factor

![](Picture4.jpg)
Bwg =                       , bbl res. gas/STB
VP,T ft3/lb-mole reservoir gas is expressed as 1.911 ZT/P bbl/lb-mole reservoir gas

PV = ZnRT
V/n = ZRT/P = [10.732 ZT/5.615] bbl/lb-mole
240

### Notes:

<!-- Slide number: 241 -->
lb-mole of reservoir gas per lb-mole of stock tank condensate is –

![](Picture1026.jpg)
one lb-mole of stock tank condensate is –

STB
241

### Notes:

<!-- Slide number: 242 -->

Bwg =

![](Picture4.jpg)
When compositions are unknown, the equation developed for nR can be used directly -

![](Picture7.jpg)
Bwg = V =

![](Picture9.jpg)
=
242

### Notes:

<!-- Slide number: 243 -->
Black oil properties
Formation Volume Factor of Oil, Bo

![j0078727](Picture4.jpg)

![bd06973_](Picture10.jpg)
Surface (Psc,Tsc)
Gas out of
Solution

![bd06973_](Picture13.jpg)

![bd06973_](Picture7.jpg)
Reservoir (P,T)
243

### Notes:

<!-- Slide number: 244 -->

![](Picture12.jpg)
Bo =
Units = Reservoir barrels  (bbl) /Stock tank barrels (STB)
Mainly three effects are involved –

Gas evolution

Pressure reduction (expansion)

Temperature reduction (contraction)
244

### Notes:

<!-- Slide number: 245 -->
General Shape of Bo

Reservoir T = constant

Bo
Pb
Reservoir Pressure
245

### Notes:

<!-- Slide number: 246 -->
Solution Gas Oil Ratio (Rs)
How much gas is dissolved in the oil volume per volume basis
Rs depends upon pressure
Units [= ] SCF gas /STB oil
246

### Notes:

<!-- Slide number: 247 -->
General Shape of Solution Gas Oil Ratio (Rs)

Reservoir T = constant

Rs
Pb
Reservoir Pressure
247

### Notes:

<!-- Slide number: 248 -->
Relation between evolved and solution GOR

![](Picture2.jpg)

248

### Notes:

<!-- Slide number: 249 -->
Total Formation Volume Factor Bt

Gas

Oil

Hg

Pb

Bg(Rsb-Rs)
Bob
Oil

Hg
Bo
249

### Notes:

<!-- Slide number: 250 -->
Definition of Bt
Also called Two-phase formation volume factor
Units…

bbl/STB + bbl/SCF * (SCF/STB)

250

### Notes:

<!-- Slide number: 251 -->
General Shape of Bt

Reservoir T = constant

Bt
Bo, Bt
Bt=Bo

Bo
Pb
Reservoir Pressure
251

### Notes:

<!-- Slide number: 252 -->
# Coefficient of isothermal compressibility
In terms of Bo –

![](Picture10.jpg)
In terms of volume

![](Picture7.jpg)
psi-1

At P < Pb

![](Picture26.jpg)

![](Picture23.jpg)
Co =
At P > Pb, Rs = constant
252

### Notes:

<!-- Slide number: 253 -->
# Oil viscosity
Two regions of oil viscosity; 1) above the bubble point pressure, and 2) below the bubble point pressure
Viscosity reduces with pressure reduction at P > Pb (gas remains in solution)
Viscosity, however, increases with decreasing pressures at P < Pb (Rs decreases; gas comes out of solution taking the lighter components with it)
Significant property in terms of EOR processes, especially those involving CO2 sequestration
253

### Notes:

<!-- Slide number: 254 -->
Variation of Oil Viscosity

T = constant

Gas Out of
Solution
Oil Viscosity
Two Phase Flow
Single Phase Flow

Pb
254

### Notes:

<!-- Slide number: 255 -->
One of the ANS heavy oil viscosity at 71.6oF

![](Picture1.jpg)
255

### Notes:

<!-- Slide number: 256 -->
# Surface tension
Almost equally affected by the properties of the two phases, such as their compositions and densities
Effect of pressure and temperature is reflected through the compositions and densities of the gas and liquid phases
Gas-oil surface tension is obviously zero at P > Pb
Important property from the point of view of miscible gas injection processes; used in the determination of capillary numbers
256

### Notes:

<!-- Slide number: 257 -->
Variation in surface tension
257

### Notes:

<!-- Slide number: 258 -->
# Volatile oils
The definition of Bo, Rs, Co, Ct, mo, sgo are also applicable to volatile oils
However, their magnitudes differ significantly as far as volatile oils are concerned mainly due to the fact that large amount of gas evolution take place below the bubble point
Oil compressibility and viscosity are important properties
258

### Notes:

<!-- Slide number: 259 -->
Bo of Black Oil and Volatile Oil

![](Picture1026.jpg)
259

### Notes:

<!-- Slide number: 260 -->
Rs of Black Oil and Volatile Oil

![](Picture2.jpg)
260

### Notes:

<!-- Slide number: 261 -->
# Laboratory tests
Although water is present together with hydrocarbons, its effect on fluid properties is ignored and tests are conducted in the absence of water
Similarly, the effect of porous media is also ignored, under the assumption that fluids will exhibit similar behavior within the porous media and in bulk (such as in a PVT cell)
Above not true for nanosized porous media – confinement effects alter phase behavior and properties
261

### Notes:

<!-- Slide number: 262 -->
# Contd.
Following the production process – most laboratory tests are depletion experiments
Pressure of the reservoir fluid is lowered in successive steps either by expanding the sample or increasing the fluid volume
Properties of the single phase fluid and the equilibrium phases formed below saturation pressure are measured so that the required reservoir engineering properties are finally determined
Specialized PVT equipment capable of handling high pressure and high temperature conditions are employed to conduct the reservoir fluid studies
262

### Notes:

<!-- Slide number: 263 -->
# PVT equipment
Basically of two types, i.e., 1) gas condensate equipment, and 2) oil equipment
The standard P and T limits these days are 15,000 psi and 400oF
Gas condensate equipment are typically large volume (to allow room for expansion)
Oil equipment are typically small volume (due to oil incompressibility)
Multipurpose equipment can handle almost all types of reservoir fluids
Essential components include a mechanism of varying pressure (or fluid volume), maintenance of constant temperature, measurement of P, V, T
263

### Notes:

<!-- Slide number: 264 -->
# Basic PV measurement

![](Picture4.jpg)

264

### Notes:

<!-- Slide number: 265 -->
# Gas condensate equipment

![](Picture4.jpg)

265

### Notes:

<!-- Slide number: 266 -->
Oil equipment

![](Picture1030.jpg)

![](Picture1034.jpg)
PVT cell
Cell control

![](Picture1032.jpg)
Displacement pump
266

### Notes:

<!-- Slide number: 267 -->
# Specialized PVT equipment

![](Picture12.jpg)
Transportable mini PVT
apparatus for saturation pressure
measurement,
can be transported to field locations
267

### Notes:

<!-- Slide number: 268 -->
# Multipurpose PVT equipment

![](Picture3.jpg)
268
ST France

### Notes:

<!-- Slide number: 269 -->
Additional capabilities of PVT equipment
High pressure density measurement of various fluid phases using the external cell Anton-Paar densitymeter
Surface tension measurement using the pendant drop technique
Viscosity measurement using the rolling ball viscometer or the capillary tube viscometer
269

### Notes:

<!-- Slide number: 270 -->
External cell Anton-Paar densitymeter

![](Picture2.jpg)
Densitymeter is calibrated with high pressure
gases and liquids of known density
270

### Notes:

<!-- Slide number: 271 -->
Surface or Interfacial tension

![ift_measure3](Picture5.jpg)

ds

de

Liquid droplet

Equilibrium vapor
271

### Notes:

<!-- Slide number: 272 -->
Rolling ball viscometry

![](Picture5.jpg)

moil = [t(rball – roil) – a] b
272

### Notes:

<!-- Slide number: 273 -->
Capillary tube viscometry

![](Picture3.jpg)

![](Picture8.jpg)

273

### Notes:

<!-- Slide number: 274 -->
# Constant composition expansion (CCE)
Also known as constant mass expansion
Other names are flash vaporization, flash liberation, flash expansion or simply pressure-volume (PV) relation
Carried out on all reservoir fluids
Overall composition and sample mass remains constant throughout the test
At constant temperature, pressure is reduced by expanding the sample; saturation pressure is measured, total and phase volumes are also measured below the saturation pressure
At the end volume of liquid at standard conditions is determined
274

### Notes:

<!-- Slide number: 275 -->
CCE for a gas condensate

![](Picture1061.jpg)
275

### Notes:

<!-- Slide number: 276 -->
PV relation for black oil and volatile oil
Flat PV curve

Sharp PV curve
276

### Notes:

<!-- Slide number: 277 -->
Y-function
The laboratory data is often evaluated, smoothed, and extrapolated by a dimensionless function Y, defined as

![](Picture1.jpg)
Vt is total volume (total cell volume in a lab test); Vb is volume at bubble point; Pb is bubble point pressure and P is some pressure below the bubble point.

A plot of Y-function versus pressure should yield a line either straight or very slightly curved.
277

### Notes:

<!-- Slide number: 278 -->
For the black oil shown on slide 74
278

### Notes:

<!-- Slide number: 279 -->
Bubble-Point of a Typical Black Oil from Qatar

![](Picture1035.jpg)
Al-Shaheen
279

### Notes:

<!-- Slide number: 280 -->
Lean gas condensate

![](Picture1026.jpg)
Optical detection technique
Dew point

280

### Notes:

<!-- Slide number: 281 -->
# Differential liberation (DL)
Also called as differential vaporization, differential depletion or differential expansion
Classical depletion experiment for reservoir oils
Gas liberated at each pressure depletion stage below bubble point is continuously removed
In the final step, cell temperature is reduced to 60oF, and the volume of remaining liquid is measured
Gas properties, oil formation volume factor, total formation volume factor are measured
281

### Notes:

<!-- Slide number: 282 -->
Oil differential liberation

![](Picture1027.jpg)
282

### Notes:

<!-- Slide number: 283 -->
# DL calculations

Z factor of produced gas –

![](Picture5.jpg)
Z =
If density and composition of gas is measured at cell conditions

n1 = lb-moles of gas at pressure stage
PR1 = (VR1rg1)/MWg1

![](Picture11.jpg)
Z1 =
Vsc1 = n1 379.6 scf
Z values used for
calculating Bg of produced gas
283

### Notes:

<!-- Slide number: 284 -->
# Contd.
BoD (D for differential liberation process), at each stage is calculated from the ratio of oil volume at cell conditions and the residual oil volume at standard conditions.  This is also referred to as relative oil volume.
RsDb (solution GOR) at P=Pb and P>Pb is given by –

![](Picture4.jpg)

284

### Notes:

<!-- Slide number: 285 -->
Contd.
RsD1 (solution GOR) at P<Pb at the first pressure stage below Pb is given by –

BtD1 (total formation volume factor) at P<Pb at the first pressure stage below Pb is given by –

![](Picture4.jpg)
BtD1 = BoD1 + Bg1(RsDb – RsD1)
285

### Notes:

<!-- Slide number: 286 -->
# Constant volume depletion (CVD)
Test designed for simulating the production behavior and separation methods of gas condensates fluids
A CCE test is first carried out to determine the dew point, at which the volume of the saturated fluid is measured
In subsequent pressure expansion steps, volume of excess gas is removed whilst maintaining the constant cell volume which is equal to the saturation volume
Excess gas removed from the cell represents the gas that is produced from the reservoir
Retrograde liquid retained in the cell represents the immobile condensate in the reservoir
CVD and DL are somewhat similar, however, not all the gas is removed from CVD
286

### Notes:

<!-- Slide number: 287 -->
Gas condensate CVD

![](Picture1026.jpg)
287

### Notes:

<!-- Slide number: 288 -->
Variation in liquid drop out
by CCE and CVD
288

### Notes:

<!-- Slide number: 289 -->
# CVD Material Balance Example

![](Picture4.jpg)

![](Picture1.jpg)
289

### Notes:

<!-- Slide number: 290 -->
# Overall Phase Balance

![](Picture5.jpg)
290

### Notes:

<!-- Slide number: 291 -->
Component Balance

![](Picture3.jpg)

![](Picture4.jpg)
291

### Notes:

<!-- Slide number: 292 -->
# Contd.

![](Picture4.jpg)

![](Picture6.jpg)

292

### Notes:

<!-- Slide number: 293 -->
# Condensate Compositions Calculated from Material Balance

![](Picture4.jpg)
293

### Notes:

<!-- Slide number: 294 -->
# Comparison of measured and calculated condensate compositions
Step 6
1160 psig
294

### Notes:

<!-- Slide number: 295 -->
# Separator tests
Laboratory tests designed to simulate potential production separator stages and provide volumetric and other information on the stock tank oil and liberated gas streams
Few pressure steps are used, temperature is also varied (usually the average field condition)
For black oils usually two separation stages are used, one representing the separator and the other a stock tank
For oils containing high GOR’s upto three separation stages are used
295

### Notes:

<!-- Slide number: 296 -->
# Contd.
Three main parameters are determined for a pressure reduction path of –

				Pres (Pb)PsepPatm

Formation volume factor of oil, BoSb
Solution gas oil ratio, RsSb
Specific gravity of the stock tank oil, oAPI

![](Picture5.jpg)
BoSb =
, res. bbl/STB

![](Picture10.jpg)
RsSb =
, scf/STB
296

### Notes:

<!-- Slide number: 297 -->
# Contd.
Primary objective of the separator test is to determine the optimum separator conditions that will give –
A minimum of the total gas oil ratio
A maximum in the API gravity of stock tank oil
A minimum in formation volume factor of oil at bubble point conditions
Subscript ‘S’ is used to denote the values measured from a separator test
297

### Notes:

<!-- Slide number: 298 -->
# Representation of separator test

![](Picture6.jpg)
298

### Notes:

<!-- Slide number: 299 -->
# Optimum separator conditions

![](Picture6.jpg)

McCain
Optimum conditions

299

### Notes:

<!-- Slide number: 300 -->
# Adjustment of black oil laboratory data
No single laboratory test alone adequately represents or describes the properties of a black oil from the reservoir to the surface
Actual reservoir process is neither constant composition expansion, nor differential liberation
Results from CCE, DL and separator tests (optimum conditions) are combined with a bubble point constraint (i.e., for reservoir pressure above and below Pb), in such a manner that the combined data may be closest to the reservoir process
300

### Notes:

<!-- Slide number: 301 -->
Phase transition in an undersaturated oil reservoir

![](Picture2.jpg)
301
Danesh

### Notes:

<!-- Slide number: 302 -->
# Nomenclature for adjustment
BoD = relative oil volume by differential liberation

BoDb = relative oil volume at bubble point by differential liberation

BoSb = formation volume factor at bubble point from separator tests (optimum or selected)

      			    = relative total volume (gas and oil) by constant composition expansion
	or 	flash vaporization, where Vt is the total volume, and Vb is the volume at    	saturation conditions or bubble point

BtD = relative total volume (gas and oil) by differential liberation

RsD = gas remaining in solution by differential liberation

RsDb = gas in solution at bubble point (and all pressures above) by differential liberation

RsSb = sum of separator gas and stock tank gas from separator tests (optimum or selected)
D, F and S represent the DL, CCE & Separator; subscript ‘b’ refers to Pb
302

### Notes:

<!-- Slide number: 303 -->
# Adjusted Bo
At P > Pb; CCE and separator test are combined

Bo =	 	   BoSb

![](Picture8.jpg)
Bo units are reduced to res. bbl of oil at pressure P/STB
303

### Notes:

<!-- Slide number: 304 -->
Adjusted Bo
At P < Pb; DL and separator test are combined

Bo =

![](Picture8.jpg)
Bo units are reduced to res. bbl of oil at pressure P/STB
304

### Notes:

<!-- Slide number: 305 -->
Adjusted RS

At P > Pb;
Rs = RsSb, scf/STB

At P < Pb; DL and separator test are combined

![](Picture6.jpg)
Rs =
Rs units are reduced to scf/STB
305

### Notes:

<!-- Slide number: 306 -->
Adjusted Bt
Adjusted Co and Ct

At P > Pb;
Bt = Bo, res. bbl/STB
Co and Ct can be calculated
on the basis of adjusted Bo and Rs values

At P < Pb;

Bt = Bo + Bg(Rsb – Rs)

      Or, Bt =

![](Picture9.jpg)
306

### Notes:

<!-- Slide number: 307 -->
Specialized PVT tests
307

### Notes:

<!-- Slide number: 308 -->
Definition of concepts
Gas cycling – carried out in gas condensate reservoirs to recover the precipitated liquid drop out that results from pressure depletion below the dew point
First contact miscibility (FCMP ) – single phase achieved no matter in what proportions the oil and gas are mixed
Carried out on undersaturated fluids (Pres > Pbubble)
Because of this condition oil has capacity to dissolve more gas
Actual laboratory test sometimes referred to as swelling test
308

### Notes:

<!-- Slide number: 309 -->
Contd.
Vaporizing gas drive (miscibility achieved at the leading edge) –
Miscibility is achieved at some distance from the injection well
At the injection well, both gas and liquid are in equilibrium
Referred to as vaporizing drive because gas takes up components from oil
Compared to injection gas, equilibrium gas phase contains more intermediate components and is rich
Equilibrium gas phase has higher mobility and it keeps enriching itself by contact with virgin oil as it moves and attains miscibility

309

### Notes:

<!-- Slide number: 310 -->

![](Picture2.jpg)
Gas-oil front or leading edge
Oil here may become
somewhat heavier
310
Pedersen and Christensen, 2007

<!-- Slide number: 311 -->
Contd.
Condensing gas drive (miscibility achieved at the trailing edge) –
Miscibility is achieved at or near the injection well
Original oil and injection gas are not miscible but miscibility may be developed at a later time
Referred to as condensing drive because gas loses components to the oil
Reservoir oil becomes lighter due to intake of components from the injection gas
Eventually the injection gas is rich, and so is the oil which develops into miscibility at or near the injection well

311

### Notes:

<!-- Slide number: 312 -->

![](Picture2.jpg)
Trailing edge
312
Pedersen and Christensen, 2007

<!-- Slide number: 313 -->
Contd.
Minimum Miscibility Pressure (MMP) – the lowest pressure where, at fixed temperature, miscibility may be achieved between a given reservoir fluid and a given injection gas
Minimum Miscibility Enrichment (MME) –
Closely related to MMP
Determines the enrichment level of a particular component or group of components in a multicomponent injection gas for a given pressure that causes the displacement to become multicontact miscible
313

### Notes:

<!-- Slide number: 314 -->
Contd.
Conceptually, MMP and MME are same; they describe the same physical mechanism, one from the point of view of varying pressure to achieve miscibility, the other from the point of view of varying injection gas composition
314

### Notes:

<!-- Slide number: 315 -->
Laboratory tests
Gas cycling
Swelling for simulation of FCM
Slim tube test for determination of MMP
Forward and backward multiple contact tests for simulation of vaporizing and condensing drive processes
This data type of data is excellent to actually calibrate or tune the EOS models
315

### Notes:

<!-- Slide number: 316 -->
Gas cycling tests
Not really a miscible process per-se, but injection gas vaporizes some of the components from the retrograde liquid
Typically a CVD is carried out first and the condition of maximum liquid drop out is determined  - which is really the target for recovery
The producing gas (after the injected gas has contacted the condensate) is enriched by the vaporized condensate
The produced gas is stripped of its intermediate and heavy components and is injected back into the reservoir
The cycling process is terminated when no more mass transfer takes place between the injection gas and the condensate
The produced gas volume and composition, and the condensate shrinkage are measured in the laboratory
316

### Notes:

<!-- Slide number: 317 -->
Condensate shrinkage

No more mass transfer
Condensate volume

Cumulative volume of injection gas
317

### Notes:

<!-- Slide number: 318 -->

![](Picture7.jpg)
North Sea gas condensate
Cycling gas is methane
318

### Notes:

<!-- Slide number: 319 -->
Swelling test schematic

![](Picture78.jpg)
319

### Notes:

<!-- Slide number: 320 -->
Slim tube

![](Picture3.jpg)
Considered as an ‘industry standard’
Unfortunately, there is no standard with respect to design and operating procedures
Asphaltene precipitation can distort the results
1D model reservoir
packed with sand or glass beads
tube length, 5-40 m
0.25 in diameter
320

### Notes:

<!-- Slide number: 321 -->

P2

P1
PV recovered %

P2 > P1
PV injected %
Tube is initially saturated with oil at reservoir temperature above bubble point pressure
Gas injection begins at constant inlet or outlet pressure
Recovery and effluent properties are measured
Injection carried out at different displacement pressures

Gas BT

321

### Notes:

<!-- Slide number: 322 -->
MMP criteria

90% ultimate oil recovery

Ultimate recovery, % PV
MMP
Displacement pressure
322

### Notes:

<!-- Slide number: 323 -->
Rising bubble
Visual demonstration of miscibility
Shape of the gas bubble rising through oil column is monitored
At P < MMP, bubble retains its spherical shape, but its size reduces due to partial dissolution in oil
At P > MMP bubble disperses rapidly and disappears in the oil

![](Picture3.jpg)
323

### Notes:

<!-- Slide number: 324 -->
Forward contact tests
Test temperature = Tres.
Injection gas

Reservoir
oil at Psat

Equi. vapor
Fresh oil
(Reservoir
oil at Psat)

Equi. oil

Oil out
1) Simulates conditions at the leading edge of injection process
2) Equi. vapor in each stage brought in contact with original oil (fresh oil)
3) Procedure generally continues until injection gas becomes miscible with original oil
4) Volume, density, compositions, viscosity, IFT measured in each contact

324

### Notes:

<!-- Slide number: 325 -->
Equilibrium gas becoming progressively richer
325

### Notes:

<!-- Slide number: 326 -->
Backward contact tests
Test temperature = Tres.
Injection gas

Gas out

Reservoir
oil at Psat

Equi. vapor
Fresh
injection
gas

Equi. oil
1) Simulates conditions at the trailing edge of injection
2) Fresh injection gas brought in contact with equilibrated oil
3) Procedure generally continues until injection gas becomes miscible with original oil
4) Volume, density, compositions, viscosity, IFT measured in each contact

326

### Notes:

<!-- Slide number: 327 -->
Illustrating miscibility
Ternary diagrams used to illustrate miscibility
Composition of a petroleum mixture is represented by 3 groups; light (C1+CO2+N2), intermediate (C2-C6), and heavy (C7+)
Each corner represents 100% of a given group
The injection gas mixture and oil are represented by two points on the ternary diagram
The two phase region is also shown on the ternary diagram
Tangent to the two phase area region at the critical point is called as critical tie line
Location of the points corresponding to the reservoir fluid composition and the injection gas, relative to the critical tie line determines miscibility
327

### Notes:

<!-- Slide number: 328 -->

![](Picture3.jpg)
328

### Notes:

<!-- Slide number: 329 -->

![](Picture3.jpg)
329

### Notes:

<!-- Slide number: 330 -->

![](Picture3.jpg)
330

### Notes:

<!-- Slide number: 331 -->

![](Picture3.jpg)
331

### Notes:

<!-- Slide number: 332 -->
Black oil correlations – if some basic field data is available and none from lab

![](Picture4.jpg)
Surface tension, s
332

### Notes:

<!-- Slide number: 333 -->

![](Picture1.jpg)
Most black oil correlations (including for MMP) are empirical – OK substitute for lab data
Developed for oils of particular geographic origin
Explicit compositional effects are largely ignored
Correlations treat the oil system as composed of mainly two components, i.e., a stock tank oil and the liberated gas
Stock tank oil and the liberated gas are characterized by their specific gravities (typical input along with temperature and solution GOR)
If the oils are “typical” then the correlations may be OK, but not recommended for volatile oils
Table compiled in Danesh (1998) book on PVT and phase behavior of petroleum reservoir fluids
333

### Notes:

<!-- Slide number: 334 -->

![](Picture2.jpg)
Evaluated Standing and Vasquez-Beggs correlations for Cook Inlet Basin oils for Pb, Rs, Bob and µob
Suggested some correction factors due to the presence of unusually large concentration of N2 in these oils
Also has a convenient compilation of the functional forms of the tested correlations
334

### Notes:

<!-- Slide number: 335 -->
# HYDROCARBON VAPOR LIQUID EQUILIBRIA
335

### Notes:

<!-- Slide number: 336 -->
# Introduction to VLE

One phase

Vapor and liquid
phases in equilibrium
One phase
Pressure
X and Y ??
Moles ??

Where ?
In reservoir & surface
Temperature
336

### Notes:

<!-- Slide number: 337 -->
# Raoult’s law and Dalton’s law
Raoult’s law applied to ideal liquid mixture (for component i) –
					Pi = XiPvi
Dalton’s law applied to ideal gas mixture (for component i) –
					Pi = YiP

![](Picture4.jpg)
Equilibrium ratio, partitioning of component in vapor and liquid phases
337

### Notes:

<!-- Slide number: 338 -->
# Concept of PT flash
nv moles of vapor having
composition Yi

Vapor

n moles of feed having
composition Zi
(P,T)

Liquid

nL moles of liquid having
composition Xi
338

### Notes:

<!-- Slide number: 339 -->
# Material balance equations
Overall material balance
				n = nL + nV
Written in terms of ith component
			    Zin = XinL + YinV
With basis as 1 mole of feed
			       nL + nV = 1
			    XinL + YinV = Zi
Use equilibrium ratio
			Xi(1- nV) + KiXinV = Zi

339

### Notes:

<!-- Slide number: 340 -->
# Flash calculation functions

![](Picture6.jpg)

![](Picture7.jpg)
Known as the Rachford–Rice flash function

![](Picture2.jpg)

![](Picture1.jpg)
–        = 0
340

### Notes:

<!-- Slide number: 341 -->
# Calculation of bubble point pressure
Already known, feed is liquid

![](Picture4.jpg)
Calculate on the basis of newly formed vapor phase

![](Picture6.jpg)
Using ideal solution principle

![](Picture8.jpg)

![](Picture9.jpg)
Pb =

341

### Notes:

<!-- Slide number: 342 -->
Calculation of dew point pressure
Already known, feed is vapor

![](Picture3.jpg)
Calculate on the basis of newly formed liquid phase

![](Picture6.jpg)
Using ideal solution principle

![](Picture9.jpg)
Pd =

![](Picture7.jpg)

342

### Notes:

<!-- Slide number: 343 -->
Ideal solution principle
and an EOS model
Lightest component in this mixture is propane–pure component does not have a vapor pressure above its Tc
Methane (Tc = –116oF) is the most volatile component in all reservoir fluids
Ideal solution principle practically inapplicable

![](Picture2.jpg)
343

### Notes:

<!-- Slide number: 344 -->
Vapor-Liquid Equilibrium  Non Ideal Behavior
When evaluating VLE we use models for the equilibrium ratios (Ki-values)

Simpler models Ki = f (P,T)
low pressure applications
explicit

More complex models Ki = f(P,T,xi,yi) use equations of state EOS (current), or convergence pressure methods (earlier)
apply to low and high pressures
implicit, highly iterative
344

### Notes:

<!-- Slide number: 345 -->
Wilson equation
Requires critical properties &
acentric factors of all components
present in the mixture
Applicability is still limited to lower pressures, but serves
as a good model to obtain a starting value for EOS iterations
345

### Notes:

<!-- Slide number: 346 -->
Whitson-Torp equation
Requires critical properties &
acentric factors of all components
present in the mixture + convergence pressure (Pk)

![](Picture6.jpg)
Ki =

![](Picture9.jpg)
A =
Standing
Pk = 60

346

### Notes:

<!-- Slide number: 347 -->
# Convergence pressure
A concept used to account for the effect of overall composition on Ki values and is based on early high pressure VLE data
K-values vs. pressure at constant temperature tend to converge to Ki = 1 at a certain pressure known as convergence pressure (Pk)
This means Yi = Xi at Pk; however, this can occur only at the mixture critical point and at other conditions Pk does not physically exist (called as “apparent”)
347

### Notes:

<!-- Slide number: 348 -->
Ki values at TTc
(Fixed overall composition)
Pk
Pb
348

### Notes:

<!-- Slide number: 349 -->
Ki values at T=Tc
(Same fluid as earlier, and same overall composition)
Pk  (=Pc)

349

### Notes:

<!-- Slide number: 350 -->
Convergence pressure of binary systems
From phase rule, for a binary system to exist in 2 phases, only P and T needs to be fixed
Xi and Yi of the equilibrated phases and Ki at a P-T condition is independent of the overall or original composition of the system
Pk values for a given binary system is basically represented by its critical locus regardless of the overall mixture composition
350

### Notes:

<!-- Slide number: 351 -->
Ethane + n-heptane binary system

![](Picture1.jpg)

Legend IDs correspond to the
     respective compositions and
     phase envelopes. For e.g.,      “4” is mixture containing 77.09 mole% ethane etc.

The convergence pressure of
     8.23 MPa at 450 K is for
     ALL C2-nC7 mixtures  regardless of the composition

351
Danesh, 1998

### Notes:

<!-- Slide number: 352 -->
Critical loci (Pk) of various C1 binaries

Pk valid for all
C1-nC6 binaries
352

### Notes:

<!-- Slide number: 353 -->
Convergence pressure of multicomponent systems
Pk depends on the overall composition of the system, because the degrees of freedom are more than two
Merely specifying the P & T alone does not characterize the system
Pk at a certain temperature is valid for a fixed overall composition
Unlike binary systems, a multicomponent mixture having different overall composition will not converge at the same pressure at a given temperature
353

### Notes:

<!-- Slide number: 354 -->
7 component hydrocarbon system of two different overall compositions
At the same T = 125oF
Pk = 3000 psia

Pk = 6000 psia
354

### Notes:

<!-- Slide number: 355 -->
NGPSA  K-value charts
Natural Gas Processors Suppliers Association (NGPSA) published convergence pressure charts for Pk’s of 800, 1000, 1500, 2000, 3000, 5000, and 10000
Components covered are methane to decane, ethylene, propylene, and non-hydrocarbons, such as nitrogen and carbon dioxide
Convergence pressure is found iteratively
Interpolation may be needed among charts
Charts have been converted to correlations through complex equations – not very effective
355

### Notes:

<!-- Slide number: 356 -->
Methane Ki as a function of two convergence pressures (based on NGPSA)
356

### Notes:

<!-- Slide number: 357 -->
# Usefulness of K-value charts
K-value charts can be used to obtain equilibrium ratios for VLE calculations
Major drawback is the fact that in order to obtain the equilibrium ratios, the convergence pressure must be known before selecting the appropriate charts
Iterative procedure proposed by Hadden is used which uses a pseudo binary concept
357

### Notes:

<!-- Slide number: 358 -->
# Hadden method
Common step is the determination of weighted average Pc and Tc of the single heavy pseudo component

i = 1 is the lightest component which is excluded
Based on which the convergence pressure is determined
Basically, the idea is to express a multicomponent system into a “pseudo” binary so as to make it composition independent

![](Picture4.jpg)
Pcmw =

![](Picture5.jpg)
Tcmw =
358

### Notes:

<!-- Slide number: 359 -->
Equivalent representation of Hadden method chart
Pcmw, Tcmw

359

### Notes:

<!-- Slide number: 360 -->
# Pb, Pd and flash calculations using K-value charts, Pk
It is possible; however, the procedure becomes extremely tedious
Highly unsuitable for repetitive computations (reservoir simulation)
Several iterations and interpolations are necessary
Equivalent or pseudo binary concept is a highly simplified assumption used in representing a multicomponent mixture
No charts available for SCN fractions and plus fractions
Equations of State (EOS) have replaced this methodology
360

### Notes:

<!-- Slide number: 361 -->
# Calculation of Pb & Pd using Whitson-Torp equation
Pressure is implicit in Whitson-Torp equation – use Wilson equation as a starting value
Calculate Pk from Standing equation
Calculate K values from Whitson-Torp
Check if bubble point or dew point equation is satisfied
If not adjust the starting value and repeat calculations
361

### Notes:

<!-- Slide number: 362 -->
# Flash calculations using  Whitson-Torp equation
Directly calculate K values from Whitson-Torp equation
Perform flash calculations (iterative)
Determine a correct value of nv that satisfies the Rachford-Rice flash function
Based on the converged value of nv calculate nL and the equilibrium vapor and liquid compositions
362

### Notes:

<!-- Slide number: 363 -->
Equations of State (EOS)
Single Component Systems
EOS are mathematical relations between pressure (P) temperature (T), and molar volume (V)
Hundreds of them available starting with the famous vdW EOS
SRK and PR are the most commonly used

Multicomponent Systems
  For multicomponent mixtures in addition to (P, T & V), the overall molar composition and a set of mixing rules are needed

363

### Notes:

<!-- Slide number: 364 -->
Uses of Equations of State (EOS)
Evaluation of miscible gas injection processes
Evaluation of properties of a reservoir oil (liquid) coexisting with a gas cap (gas)
Simulation of volatile oil and gas condensate production through constant volume depletion evaluations
Recombination tests using separator oil and gas streams
Separator calculations, simulation of CCE, DL
Many more…

364

### Notes:

<!-- Slide number: 365 -->
vdW EOS
Primary objective is to eliminate the
shortcomings of ideal gas equation

![](Picture5.jpg)

![](Picture4.jpg)
or
P = Prepulsive - Pattractive
All other EOS models are modified
versions of vdW EOS
365

### Notes:

<!-- Slide number: 366 -->
PV relationship of a
pure component

Critical point

Pc
Critical
isotherm

Horizontal
inflection
point
Pressure
Saturation
curve

Volume
Vc
366

### Notes:

<!-- Slide number: 367 -->
vdW EOS parameters
Horizontal inflection point is used to
determine the EOS parameters

![](Picture5.jpg)

![](Picture6.jpg)
367

### Notes:

<!-- Slide number: 368 -->
Cubic forms of vdW EOS

Cubic in volume

![](Picture3.jpg)
Cubic in compressibility factor

![](Picture4.jpg)

![](Picture6.jpg)
A =

![](Picture7.jpg)
B =
368

### Notes:

<!-- Slide number: 369 -->
vdW loops

Critical point

Saturation curve

VM
A1 = A2
Psat
VV

Pressure
A2

A1

T = Tc
vdW loop
VL

Volume
Maxwell’s equal
area rule
369

### Notes:

<!-- Slide number: 370 -->
Other EOS models

![](Picture3.jpg)
RK

![](Picture4.jpg)
SRK

![](Picture5.jpg)
PR

Modification
of the
attractive term

370

### Notes:

<!-- Slide number: 371 -->
Cubic forms
EOS parameters a and b are determined by imposing the critical point conditions for all EOS models

PR EOS

![](Picture5.jpg)

![](Picture7.jpg)

![](Picture4.jpg)

![](Picture15.jpg)
A=

![](Picture8.jpg)

![](Picture18.jpg)
B =
m = 0.379642 + 1.48503w – 0.1644w2 + 0.016667w3

![](Picture10.jpg)
371

### Notes:

<!-- Slide number: 372 -->
# Concept of fugacity
Fugacity or fugacity coefficient is introduced as a criterion for thermodynamic equilibrium
Described as a fictitious pressure, which may be considered as a vapor pressure modified to represent correctly the escaping tendency of the molecules from one phase into the other
Fugacity coefficient

![](Picture4.jpg)
ln
F = f/P
372

### Notes:

<!-- Slide number: 373 -->
# Fugacity applied to EOS models
PR EOS, based on its cubic form in Z

![](Picture4.jpg)
ln

Same equation is applied to vapor as well as liquid phase but with their own compressibility factors, ZV and ZL
When applied to pure components, the conditions that result in equal fugacity coefficients for the vapor (FV) and liquid (FL) phase indicate that the system is in thermodynamic equilibrium
373

### Notes:

<!-- Slide number: 374 -->
# EOS application to pure components
Saturation pressure (vapor pressure) of a pure component and densities of the equilibrium phases
Calculate EOS parameters for the given component, assume a saturation pressure
Form the cubic equation in Z, solve for low (liquid) and high (vapor) roots
Using ZV and ZL calculate FV and liquid FL
If FV = FL assumed value is correct, otherwise adjust the value of pressure
From converged Z values calculate phase specific volumes and subsequently density
374

### Notes:

<!-- Slide number: 375 -->
# Extension of EOS models to mixtures
EOS models are developed for pure components which are extended to mixtures by employing mixing rules
Mixing rules calculate mixture parameters equivalent to those of pure components
In PR or SRK EOS a, b and a are component dependent constants
When working with mixtures (aa) and (b) are evaluated using a set of mixing rules
 The most common mixing rules are:
Quadratic for a
Linear for b
375

### Notes:

<!-- Slide number: 376 -->
EOS mixing rules

![](Picture4.jpg)
(aa)m =

![](Picture7.jpg)
(b)m =
kij’s are the binary interaction parameters
A and B for mixture for setting the cubic equation

376

### Notes:

<!-- Slide number: 377 -->
# Binary interaction parameters (BIP)
BIP’s are empirically determined correction factors characterizing the binary formed by component i and j in the hydrocarbon mixture
BIP’s are determined by regression analysis by matching EOS predicted and experimental saturation pressure data
BIP’s are EOS dependent
Each binary pair has different values
kij = kji and kii = 0; kC1C2 < kC1nC10
Often used in tuning/calibrating EOS models
377

### Notes:

<!-- Slide number: 378 -->
# Single phase mixture density calculation from EOS model
Based on properties of individual mixture components calculate pure component parameters: a, b and a
Using the mixing rules and BIP’s calculate (aa) and (b) for the given mixture
Calculate A and B and set the EOS in cubic form for Z factor
Solution of cubic equation results in one real root and two imaginary roots, which have no meaning
The real Z root is used for calculating the density – the PDF handout has a solved example:

![](Picture2.jpg)

![](Picture1.jpg)
378

### Notes:

<!-- Slide number: 379 -->
Equilibrium ratios from EOS models
Fugacity of each component in the vapor and the liquid phase is used as a criterion for determining the thermodynamic equilibrium
Fugacity of a component in the vapor phase and the liquid phase is basically a measure of the potential for transfer of the component between the phases
Inequality of fugacity of a component in the vapor and liquid phase indicates further potential for mass transfer between phases
Equality in fugacity implies zero net transfer and hence thermodynamic equilibrium
379

### Notes:

<!-- Slide number: 380 -->
Contd.

![](Picture4.jpg)
For i = 1 to N

F = function(f, P, mole fractions)

![](Picture7.jpg)

![](Picture8.jpg)
Key relationship
for VLE calculations

![](Picture12.jpg)
Ki =

![](Picture11.jpg)

380

### Notes:

<!-- Slide number: 381 -->
Generalized expression for fugacity
coefficient of ith component
Valid for both PR and SRK EOS

![](Picture3.jpg)
ln
d1 = 0 & d2 = 1 for SRK
d1 =

![](Picture17.jpg)

![](Picture18.jpg)
d2 =
for PR

&

![](Picture8.jpg)

![](Picture9.jpg)
=

![](Picture12.jpg)
Identical equations
set up for liquid phase but using liquid phase
parameters
381

### Notes:

<!-- Slide number: 382 -->
# VLE calculations using EOS models
Bubble point
Dew point
PT flash
Large number of components in petroleum reservoir fluids – instead of checking            of each and every component, an error function is used as a convergence criterion

![](Picture3.jpg)

![](Picture4.jpg)

![](Picture6.jpg)
382

### Notes:

<!-- Slide number: 383 -->
# Bubble point calculations
Start with an assumed value of bubble point
Calculate Ki values using Wilson equation as a first guess
Yi = KiXi gives the vapor phase composition
Set up EOS model for vapor and liquid phases, calculate fugacity coefficients and fugacities of all components and check the convergence criteria
If convergence criteria is not satisfied calculate new Ki values from fugacity coefficients and update the pressure and vapor phase composition for next iteration

383

### Notes:

<!-- Slide number: 384 -->
Contd.
At equilibrium

![](Picture4.jpg)

![](Picture3.jpg)

Updated pressure

![](Picture5.jpg)
Updated vapor phase composition
Yi = KiXi
Proceed to next iteration, evaluate convergence
384

### Notes:

<!-- Slide number: 385 -->
Dew point calculations
Also begin with an assumed value of dew point, calculate Ki values using Wilson equation
Xi = Yi/Ki gives the liquid phase composition
Set up EOS model for vapor and liquid phases, calculate fugacity coefficients and fugacities, check the convergence criteria
If convergence criteria is not satisfied calculate new Ki values from fugacity coefficients and update the pressure and liquid phase composition for next iteration,               gives the updated pressure,

Remaining procedure is similar to Pb calculations

![](Picture4.jpg)
385

### Notes:

<!-- Slide number: 386 -->
# PT flash calculations
Similar to Pb and Pd calculations, except the fact that pressure is known
Begin calculations with Ki values from Wilson equation
Perform flash calculations (Rachford-Rice)
Using the calculated vapor and liquid phase compositions, the fugacity coefficients and the fugacities of each component in the vapor and liquid phase is determined
Evaluate convergence criteria; if satisfied solution has converged
Else calculate new Ki values from fugacity coefficients and proceed to next iteration
386

### Notes:

<!-- Slide number: 387 -->
PT flash calculation flowchart
Input Zi, P, T, Tc, Pc, w

Calculate       from Wilson equation

Flash calculations – determine Yi & Xi

Set-up EOS for vapor & liquid phases

Calculate
AND Calculate

No

Yes
Print Yi, Xi, nV, nL, VV, VL, rV, rL
387

### Notes:

<!-- Slide number: 388 -->
EOS models are not perfect…
Predicted fluid property values may differ substantially from observed laboratory data
OK for simple synthetic or model mixtures because properties of all components are well defined – obviously not the case with petroleum reservoir fluids due to the presence of SCN and plus fractions
EOS are routinely “calibrated” or “tuned“ to selected & limited experimental data and then used for other applications such as compositional reservoir simulation with some confidence

388

### Notes:

<!-- Slide number: 389 -->
What is EOS calibration?
Minimization of squared differences between experimental and predicted fluid properties

These properties (gi) include:
Densities, saturation pressures (most common)
Relative amounts of gas and liquid phases
Compositions
Quality of the experimental data is important
389

### Notes:

<!-- Slide number: 390 -->
Contd.
There is no “standard” tuning procedure – a bit of trial and error
Adjustments of binary interaction parameters (kij)
Although not recommended but may be possible to obtain a match with very slight change in even methane properties
Greatest uncertainty lies with the plus fraction and the SCN fractions – tuning focus should be on plus fraction properties such as critical properties and acentric factors
Even changing plus fraction properties should be within known experimental uncertainties (for e.g., molecular weight measurement uncertainty within 10%) and MW is used to obtain Tc, Pc, Vc etc.

390

### Notes:

<!-- Slide number: 391 -->
Saturation pressure match

Measured
EOS

Pressure
If available – match Pb/Pd
at reservoir temperature and
few others in the vicinity to
capture the shape
Temperature
391

### Notes:

<!-- Slide number: 392 -->
# PVT simulators
CMG WinPROP, tNavigator PVT Designer etc. can easily do the EOS tuning

![](Picture2.jpg)

![](Picture1.jpg)
Changing  of C7+ matches Pb

![](Picture5.jpg)
392

### Notes:

<!-- Slide number: 393 -->
# Stability analysis
Deals with an important question of a given mixtures’ ability to attain lower energy by splitting into 2 or more phases or by remaining at a lower energy as a single phase.
Since there can be 3 real roots of Z factor, the one that gives the lowest overall system Gibbs energy (shown for PR EOS) is chosen for fugacity calculations

![](Picture1.jpg)
G/RT =
393

<!-- Slide number: 394 -->
Normalized Gibbs energy function, g*, defined by Whitson and Brule is used to calculate multiple composition dependent values of g*, which are plotted vs. mole fraction of the lightest component in the mixture (a binary) to determine the valleys (if any). This potentially shows the attainment of lower energy by the mixture splitting into two phases.
Zi and fi are mole fraction and fugacity (at the chosen Z factor) of component i, calculated from the following (shown for PR EOS)
394

<!-- Slide number: 395 -->

Other parameters appearing in above expression are standard definitions for a given EOS (PR in this case).
Note that in this Gibbs analysis the idea is to scan the entire compositional space to identify the valleys. This is the “graphical stability analysis concept” originally proposed by Baker et. al. (somewhat limited to binary systems because for 3+ components it becomes a hyper-surface or hyper-plane). But works if a pseudo–binary concept is assumed. This was modified later by Michelsen as an algorithm.
395

<!-- Slide number: 396 -->
# 40 mole% C1 and 60 mole% CO2 binary system

![](Picture4.jpg)
396
Phase envelope from Pedersen et. al.

<!-- Slide number: 397 -->
# Gibbs energy surface for the C1-CO2 binary at −42°C and 20 bar
Gibbs tangent plane at the two valleys, which give the liquid and vapor phase mole fractions respectively and the PHASE mole fractions determined from Lever rule

![](Picture14.jpg)
397

<!-- Slide number: 398 -->
# Comparison with traditionally done flash calculations

![](Picture4.jpg)
The above (using SRK EOS) compares quite well with the values obtained from the Gibbs energy surface or stability analysis (using PR EOS) shown on previous slide.
398
Flash calculations from Pedersen et. al.

<!-- Slide number: 399 -->
# VLE of CO2-heavy oil systems (pseudo-binary concept used)
Canadian heavy oil in which CO2-oil treated as a pseudo binary. Stability analysis liquid (dominated by the heavy hydrocarbon phase) & vapor (dominated by CO2) compositions compare very well with traditionally done flash calculations.
Fixed T & P
399

<!-- Slide number: 400 -->
# Another CO2-heavy oil system with pseudo-binary concept

### Chart

| Category |  |
|---|---|Brazilian heavy oil in which CO2-oil treated as a pseudo binary. Stability analysis liquid (dominated by the heavy hydrocarbon phase) & vapor (dominated by CO2) compositions compare very well with traditionally done flash calculations.
Fixed T & P
400

<!-- Slide number: 401 -->
# Phase behavior under confinement
Shale based fluids reside and also flow in very low nano-darcy permeability range rocks.
Very low permeability also known as “confinement “
In conventional systems (20 – 200 μm average pore size) phase behavior in bulk and within pores assumed to be the same, i.e., PVT data obtained in a PVT cell obviously in the absence of porous media.
In unconventionals phase behavior in bulk ≠ phase behavior under confinement.
Difference ascribed to the intimate interaction between the fluid and the wall of the pore (kerogen). The molecular interaction being somewhat random in bulk as opposed to orderly and layered in nano pores, which can cause alterations in the thermodynamic properties (critical constants) and fluid phase behavior.
Where do you draw the line? When the pores are typically less than 10 nm. In shale reservoirs, the common pore size distribution ranges between ~ 1 – 20 nm with dominant pore diameters smaller than 2 nm.
401

<!-- Slide number: 402 -->
# Use capillary pressure in flash calculationsto account for confinement
In a PVT cell (bulk) at equilibrium PGas = PLiqiuid = PSat. because the interface is flat or the curvature is zero.
Generally speaking, in the case of any porous media for that matter, a non-zero curvature of the gas – liquid interface will result in a pressure difference between the two phases, i.e., Pc such that PGas – PLiquid ≠ 0, but is = Pc. But these are low for conventional porous media hence ignored.
Bulk data needs to be scaled according to the level of confinement, because as of yet capabilities to obtain all the fluid behavior information directly or in-situ in a laboratory setting, do not exist. There are few limited studies.
Numerically done by shifting the critical constants of the fluid constituents OR by incorporating Pc in EOS calculations (more common).
402

<!-- Slide number: 403 -->
# Fundamental Pc equation
Need (1) gas – oil IFT, a function of compositions and densities (output of flash calculations) if parachor method is used; (2) contact angle and (3) average pore radius.

Can be simplified by assuming liquid (L) or oil (O) as fully wetting, i.e., GO = 0 or CosGO = 1

Computations become highly iterative
403

<!-- Slide number: 404 -->
# Equilibrium ratio and Rachford-Rice flash function
With confinement included (reduces to Ki if PcGO is ignored, i.e., PG = PO)
needs to be modified because fugacities are calculated using the respective phase pressures, which are not the same
Normal iterative sequence
&
At equilibrium
This naturally reduces to
If Pc is ignored, PG = PO = PL
404

<!-- Slide number: 405 -->
Same Wilson equation can be applied if “altered” Tc and Pc are used:
Bubble point constraint			Dew point constraint
The PDF handout has very detailed step-by-step calculations

![](Picture2.jpg)

![](Picture1.jpg)
405

<!-- Slide number: 406 -->
# Bubble point calculation (C1-nC4 binary), 5nm confinement

![](Picture4.jpg)
406

<!-- Slide number: 407 -->

![](Picture4.jpg)

![](Picture6.jpg)
407

<!-- Slide number: 408 -->
# Converged bubble point calculations
408

<!-- Slide number: 409 -->
409

<!-- Slide number: 410 -->
410

<!-- Slide number: 411 -->
411

<!-- Slide number: 412 -->
# Dew point calculation (C1-nC4 binary), 7.5nm confinement

![](Picture4.jpg)
412

<!-- Slide number: 413 -->
413

<!-- Slide number: 414 -->
# Comparison with the “only” available real dew point measurement under confinement
414

<!-- Slide number: 415 -->
# EOS SIMULATION OF LABORATORY PVT TESTS
415

### Notes:

<!-- Slide number: 416 -->
# Basic EOS calculations
Saturation pressure
PT flash
Saturation volume
Mole fractions of equilibrium phases and their respective compositions
Equilibrium phase and single phase densities
Based on all the above the reservoir engineering properties (Bg, Bo, Rs, Co, Bt) are calculated
Viscosities, surface tensions, thermal conductivity etc. are also calculated but based on the compositional and density data from models such as the LBC, Parachor, Corresponding states etc.
In EOS calculations everything is simulated on the basis of a mole or unit volume of original reservoir fluid
416

### Notes:

<!-- Slide number: 417 -->
# Simulation of CCE
Given Zi and T

Calculate Pb or Pd

Assume n = 1; remains constant

Calculate Vsat based on ZV or ZL from EOS

Increase pressure in steps P > Psat and calculate V

Decrease pressure; P < Psat, Xi, Yi, nV, nL, rV, rL, ZV, ZL

Calculate VV and VL and Vtotal

PV relationship
417

### Notes:

<!-- Slide number: 418 -->
# Example of CCE simulation
Take a binary system of methane and n-hexadecane of
50 mole % each at 300OF

Calculated saturation pressure (bubble point in this case)
is 3129.081 psia
In the calculation of Psat, ZL is obviously calculated
using the convergence criteria; this value is 1.3422
418

### Notes:

<!-- Slide number: 419 -->
# Contd.
Raise the pressures above Psat, and calculate ZL
values which are obviously the only meaningful
roots in single phase. Using these calculate volumes.
| P, psia | ZL | V, ft3 |
| --- | --- | --- |
| 5000 | 2.0775 | 3.387479 |
| 4750 | 1.9807 | 3.399623 |
| 4500 | 1.8835 | 3.412391 |
| 4250 | 1.7859 | 3.425893 |
| 4000 | 1.6878 | 3.440065 |
| 3750 | 1.5892 | 3.455039 |
| 3500 | 1.4902 | 3.47122 |
| 3250 | 1.3906 | 3.488386 |
419

### Notes:

<!-- Slide number: 420 -->
# Contd.
Reduce the pressures below Psat, perform two phase flash calculations and based on convergence criteria ZV and ZL values are known. Using these values and nV and nL (fraction because basis is 1 lb-mole of reservoir fluid) calculate phase volumes. Since this is CCE nL+nV = 1.
| P, psia | ZL | ZV | nL | nV | VL, ft3 | VV , ft3 | Vtotal , ft3 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 250 | 0.1758 | 0.9905 | 0.529676 | 0.470324 | 3.03665 | 15.19208 | 18.22873 |
| 500 | 0.3353 | 0.9826 | 0.561591 | 0.438409 | 3.07036 | 7.024119 | 10.09448 |
| 750 | 0.48 | 0.9761 | 0.594808 | 0.405192 | 3.103576 | 4.299318 | 7.402894 |
| 1000 | 0.6115 | 0.9709 | 0.629502 | 0.370498 | 3.138334 | 2.932689 | 6.071023 |
| 1250 | 0.731 | 0.967 | 0.665768 | 0.334232 | 3.174212 | 2.107998 | 5.28221 |
| 1500 | 0.8396 | 0.9643 | 0.7037 | 0.2963 | 3.211252 | 1.552953 | 4.764204 |
| 1750 | 0.9384 | 0.9629 | 0.743397 | 0.256603 | 3.249948 | 1.151093 | 4.401041 |
| 2000 | 1.0283 | 0.9626 | 0.784971 | 0.215029 | 3.290403 | 0.843759 | 4.134162 |
| 2250 | 1.11 | 0.9635 | 0.828549 | 0.171451 | 3.332455 | 0.59857 | 3.931025 |
| 2500 | 1.1842 | 0.9655 | 0.874275 | 0.125725 | 3.376282 | 0.395858 | 3.77214 |
| 2750 | 1.2517 | 0.9685 | 0.922314 | 0.077686 | 3.422567 | 0.223057 | 3.645624 |
| 3000 | 1.3129 | 0.9725 | 0.972855 | 0.027145 | 3.471076 | 0.07174 | 3.542817 |
420

### Notes:

<!-- Slide number: 421 -->
# Relative volume
421

### Notes:

<!-- Slide number: 422 -->
# Phase densities
From volumetrics, mole fractions, and compositions
422

### Notes:

<!-- Slide number: 423 -->
# Simulation of DL
Zi, Psat, T and ni = 1

Flash calculations @ P1 < Psat; n’s, Z’s, V’s, X1, Y1

Flash calculations (P2 < Psat) using X1 as feed
and ni = nLbecause all gas is removed
Composition data goes for ST and
viscosity calculations

Same information and calculations as previous 2 boxes
n pressure steps
Flash calculations @ SC; feed is oil comp. from last
pressure step at 1 atm and T (res.)

Vo(SC) and rSC

Bt, calculated from equation

Vgas@SC =nV*379.6

423

### Notes:

<!-- Slide number: 424 -->
# Example of DL simulation
Same binary system of CCE
PT flash at 3000 psia (below Pb) results in 0.972855 moles of liquid and 0.027145 moles of gas (10.3 scf); Bg of 0.00124 bbl/scf
VL is 3.471076 ft3 and liquid phase composition is 48.61 and 51.39 mole % of C1 and nC16
Above composition and liquid moles of 0.972855 is the feed for next pressure step (2500 psia) flash
This results in 42.84 and 57.16 mole% of C1 and nC16; 0.8987 moles of liquid and 0.1013 moles of gas.  But moles of gas = 0.1013*0.972855 = 0.0986; which is 37.79 scf and Bg = 0.00147 bbl/scf
VL is calculated from ZL and nL = 0.8987*0.972855; which is 3.376 ft3

424

### Notes:

<!-- Slide number: 425 -->
# DL mole balance using EOS
0.027 moles out
Mole fractions

Actual moles

0.101

0.101*0.973
= 0.098
0.899

0.899*0.973
= 0.875

0.098 moles out
Mole fractions

Actual moles

0.027

0.027
0.973

0.973

ni = 1

3000 psia
0.973

0.089 moles out

2500 psia

Actual moles used for volume calculations
Mole fractions

Actual moles

0.102

0.102*0.875
= 0.089
0.898

0.898*0.875
= 0.785

Summation of all removed
gas moles equals to 0.4993
0.875, 2000 psia

Mole fractions

Actual moles

0.000

0.00*0.5007
= 0.00
1.000

1.00*0.5007
= 0.5007

0.4993 gas moles plus
0.5007 remaining moles
of liquid equals 1; that is
what we started with

Correct mole balance
is the key for these
calculations!

After other pressure steps; 14.7 psi and 60oF
425

### Notes:

<!-- Slide number: 426 -->
# From flash calculations
| Pressure, psia | Feed X, mol % C1 nC16 |  | nL mol frac. | nV mol frac. | ZL | ZV |
| --- | --- | --- | --- | --- | --- | --- |
| 3000 | 48.61 | 51.39 | 0.973 | 0.027 | 1.313 | 0.973 |
| 2500 | 42.84 | 57.16 | 0.899 | 0.101 | 1.184 | 0.966 |
| 2000 | 36.35 | 63.65 | 0.898 | 0.102 | 1.028 | 0.963 |
| 1500 | 29.00 | 71.00 | 0.896 | 0.104 | 0.840 | 0.964 |
| 1000 | 20.63 | 79.37 | 0.894 | 0.106 | 0.612 | 0.971 |
| 500 | 11.04 | 88.96 | 0.892 | 0.108 | 0.335 | 0.983 |
| 100 | 2.33 | 97.67 | 0.911 | 0.089 | 0.072 | 0.996 |
| 14.696 | 0.34 | 99.66 | 0.980 | 0.020 | 0.011 | 0.999 |
| 14.696\* | 0.34 | 99.66 | 1.000 | 0.000 | 0.015 | - |
* 60oF; other data at reservoir temperature of 300oF
426

### Notes:

<!-- Slide number: 427 -->
# Volumes for DL calculations
| Actual moles of gas | Actual moles of liquid | Vgas, scf | VL, ft3 |
| --- | --- | --- | --- |
| 0.027 | 0.973 | 10.304 | 3.471 |
| 0.099 | 0.874 | 37.436 | 3.376 |
| 0.089 | 0.785 | 33.947 | 3.290 |
| 0.081 | 0.703 | 30.897 | 3.210 |
| 0.074 | 0.629 | 28.195 | 3.137 |
| 0.068 | 0.561 | 25.769 | 3.069 |
| 0.050 | 0.511 | 19.044 | 3.017 |
| 0.010 | 0.501 | 3.936 | 3.000 |
| 0.000 | 0.501\*\* | 0.000 | 2.795 (VoSC) |
| 0.499\* |  | 189.528 |  |
427
* Summation of total gas removed  ** liquid remaining in cell

### Notes:

<!-- Slide number: 428 -->
# DL calculations
Sample calculations

Bg = 0.005035*0.973*759.67/3000 = 0.0012 bbl/scf

Bo = 3.471/2.795 = 1.242 res. bbl/STB

RsDb = (189.528/2.795)*5.615
= 380.8 scf/STB

RsD1 = ((189.528-10.304)/2.795)*5.615 = 360 scf/STB

Bt = 1.242 + 0.0012*(380.8-360) = 1.27 scf/STB
| Bg, bbl/scf | Bo, res. bbl/STB | Rs, scf/STB | Bt, res. bbl/STB |
| --- | --- | --- | --- |
| 0.0012 | 1.2419 | 360 | 1.27 |
| 0.0015 | 1.2079 | 285 | 1.35 |
| 0.0018 | 1.1770 | 217 | 1.48 |
| 0.0025 | 1.1484 | 155 | 1.70 |
| 0.0037 | 1.1222 | 98 | 2.17 |
| 0.0075 | 1.0978 | 46 | 3.61 |
| 0.0381 | 1.0793 | 8 | 15.28 |
| 0.2601 | 1.0733 | 0 | 100.09 |
428

### Notes:

<!-- Slide number: 429 -->
# Overall results
429

### Notes:

<!-- Slide number: 430 -->
Calculations can also be carried out
with ni = 1 instead
of Vi = 1
# Simulation of CVD
Zi, Pd, T, Zd and assume Vi = Vsat. = 1

Flash calculation at P < Pd;
Get ZV, ZL, nV, nL, X and Y

Calculate actual moles
(nL)actual =ni*nL
(nV)actual, = ni*nV

All calculations within the red outline are repeated
Condition is (const. vol.):
VL+VV = 1 = Vsat.
Remove excess
gas (produced)
(Vgp)P,T = VL+VV-1
Moles of remaining gas
(nV)r = (nV)actual - np

New flash calculations

with this composition
for next pressure step

430

### Notes:

<!-- Slide number: 431 -->
# Gas condensate CCE and CVD example
Take a binary system of methane and n-butane of 77 mole % and 23 mole % respectively at 100 oF
Determine the dew point; this comes to 1963.81 psia
In the calculation of Pd, Zd (ZV) is obviously calculated using the convergence criteria; this value is 0.564
Next calculate the volume at dew point conditions, which is used for liquid drop out calculations (CCE)
Basis here is one mole of feed.  If basis is 1 unit volume at saturation conditions, then initial moles have to be calculated (as shown in this example)
431

### Notes:

<!-- Slide number: 432 -->
# CCE calculations
Data from flash calculations
|  | Pressure, psia | ZL | nL | VL, ft3 |
| --- | --- | --- | --- | --- |
|  | 1900 | 0.4660 | 0.207 | 0.305 |
|  | 1800 | 0.4305 | 0.248 | 0.357 |
|  | 1700 | 0.4018 | 0.254 | 0.360 |
|  | 1600 | 0.3761 | 0.250 | 0.353 |
|  | 1500 | 0.3521 | 0.243 | 0.343 |
|  | 1400 | 0.3290 | 0.235 | 0.331 |
|  | 1300 | 0.3065 | 0.225 | 0.319 |
|  | 1200 | 0.2843 | 0.215 | 0.305 |
|  | 1100 | 0.2621 | 0.204 | 0.292 |
|  | 1000 | 0.2400 | 0.192 | 0.277 |
|  | 900 | 0.2177 | 0.179 | 0.261 |
|  | 800 | 0.1953 | 0.165 | 0.242 |
|  | 700 | 0.1725 | 0.149 | 0.221 |
|  | 600 | 0.1494 | 0.130 | 0.195 |
|  | 500 | 0.1258 | 0.105 | 0.159 |
432

### Notes:

<!-- Slide number: 433 -->
# CCE liquid drop out
433

### Notes:

<!-- Slide number: 434 -->
# CVD calculations
Z1 (C1) = 0.77
Z2 (nC4) = 0.23
Pd = 1963.81 psia
Zd = 0.564; Vi = Vsat. = 1
ni = 1963.81/(0.564*10.732*559.67)
= 0.5797
nL = 0.2072; ZL = 0.466
nV = 0.7928; ZV = 0.597
X1 = 0.6554 & X2 = 0.3446
Y1 = 0.7995 & Y2 = 0.2005
(nL)actual = 0.5797*0.2072 = 0.1201
(nV)actual = 0.5797*0.7928 = 0.4596
Flash to 1900 psia

VL = 0.466*0.1201*10.732*559.67/1900 = 0.177 ft3
VV = 0. 597*0.4596*10.732*559.67/1900 = 0.867 ft3
Liq. Drp. Out = 17.7 % (same as CCE, only this step)

Vt = 0.177+0.867 = 1.044 ft3
Vgp = 1.044-1 = 0.044 ft3
np = 1900*0.044/(0.597*10.732*559.67)
= 0.0233; Gp = 0.0233/0.5797 = 4.02%
(nV)r = 0.4596-0.0233 = 0.4363

Feed for 1800 psia; calculations
continue according to this procedure
until the last pressure step
434

### Notes:

<!-- Slide number: 435 -->
# Detailed CVD calculations
| Pressure psia | nL, % | nV , % | ZL | ZV | (nL)actual | (nV)actual | Mole % |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  | X1 | X2 | Y1 | Y2 |
| 1900 | 20.716 | 79.28 | 0.466 | 0.5974 | 0.120 | 0.460 | 65.537 | 34.463 | 79.99 | 20.00 |
| 1800 | 25.44 | 74.6 | 0.431 | 0.6296 | 0.141 | 0.414 | 60.71 | 39.29 | 82.39 | 17.61 |
| 1700 | 27.21 | 72.8 | 0.402 | 0.6549 | 0.142 | 0.379 | 56.67 | 43.33 | 83.91 | 16.09 |
| 1600 | 28.17 | 71.8 | 0.376 | 0.677 | 0.137 | 0.350 | 52.98 | 47.02 | 85.02 | 14.98 |
| 1500 | 28.89 | 71.1 | 0.352 | 0.6974 | 0.131 | 0.323 | 49.48 | 50.52 | 85.84 | 14.16 |
| 1400 | 29.5 | 70.5 | 0.329 | 0.7166 | 0.125 | 0.298 | 46.09 | 53.91 | 86.47 | 13.53 |
| 1300 | 30.1 | 69.9 | 0.307 | 0.735 | 0.118 | 0.275 | 42.77 | 57.23 | 86.93 | 13.07 |
| 1200 | 30.74 | 69.3 | 0.284 | 0.7529 | 0.112 | 0.252 | 39.49 | 60.51 | 87.25 | 12.75 |
| 1100 | 31.46 | 68.5 | 0.262 | 0.7704 | 0.105 | 0.230 | 36.22 | 63.78 | 87.43 | 12.57 |
| 1000 | 32.28 | 67.7 | 0.24 | 0.7875 | 0.099 | 0.208 | 32.94 | 67.06 | 87.47 | 12.53 |
| 900 | 33.22 | 66.8 | 0.218 | 0.8045 | 0.093 | 0.187 | 29.65 | 70.35 | 87.35 | 12.65 |
| 800 | 34.31 | 65.7 | 0.195 | 0.8212 | 0.087 | 0.167 | 26.34 | 73.66 | 87.04 | 12.96 |
| 700 | 35.58 | 64.4 | 0.173 | 0.8377 | 0.081 | 0.147 | 22.99 | 77.01 | 86.48 | 13.52 |
| 600 | 37.08 | 62.9 | 0.149 | 0.854 | 0.076 | 0.128 | 19.59 | 80.41 | 85.59 | 14.41 |
| 500 | 38.8 | 61.2 | 0.126 | 0.8701 | 0.070 | 0.110 | 16.15 | 83.85 | 84.17 | 15.83 |
435

### Notes:

<!-- Slide number: 436 -->
# Contd.
| VL, ft3 | VV , ft3 | Vt , ft3 | Vgp , ft3 | nP | (nV)r | new ni | C1, mol. frac. (new feed) | nC4 mol. frac. (new feed) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.177 | 0.868 | 1.045 | 0.045 | 0.02378 | 0.43584 | 0.55593 | 0.7687 | 0.2313 |
| 0.203 | 0.871 | 1.074 | 0.074 | 0.03521 | 0.37927 | 0.52072 | 0.7650 | 0.2350 |
| 0.201 | 0.877 | 1.078 | 0.078 | 0.03378 | 0.34524 | 0.48694 | 0.7599 | 0.2401 |
| 0.194 | 0.889 | 1.083 | 0.083 | 0.03249 | 0.31726 | 0.45445 | 0.7534 | 0.2466 |
| 0.185 | 0.902 | 1.088 | 0.088 | 0.03136 | 0.29181 | 0.42309 | 0.7456 | 0.2544 |
| 0.176 | 0.917 | 1.093 | 0.093 | 0.03032 | 0.26796 | 0.39278 | 0.7364 | 0.2636 |
| 0.167 | 0.932 | 1.100 | 0.100 | 0.02937 | 0.24516 | 0.36341 | 0.7257 | 0.2743 |
| 0.159 | 0.949 | 1.107 | 0.107 | 0.02852 | 0.22318 | 0.33488 | 0.7132 | 0.2868 |
| 0.151 | 0.966 | 1.116 | 0.116 | 0.02766 | 0.20188 | 0.30723 | 0.6987 | 0.3013 |
| 0.143 | 0.984 | 1.127 | 0.127 | 0.02687 | 0.18120 | 0.28035 | 0.6818 | 0.3182 |
| 0.135 | 1.005 | 1.140 | 0.140 | 0.02617 | 0.16105 | 0.25419 | 0.6621 | 0.3379 |
| 0.128 | 1.029 | 1.157 | 0.157 | 0.02552 | 0.14145 | 0.22867 | 0.6389 | 0.3611 |
| 0.120 | 1.059 | 1.179 | 0.179 | 0.02493 | 0.12237 | 0.20373 | 0.6112 | 0.3888 |
| 0.113 | 1.096 | 1.209 | 0.209 | 0.02444 | 0.10376 | 0.17929 | 0.5778 | 0.4222 |
| 0.105 | 1.147 | 1.252 | 0.252 | 0.02411 | 0.08561 | 0.15518 | 0.5368 | 0.4632 |
436

### Notes:

<!-- Slide number: 437 -->
# Overall results
437

### Notes:

<!-- Slide number: 438 -->
# Separator calculations using EOS
Separator calculations performed to determine the optimum separator conditions based on EOS models predominantly involve PT flash calculations
In a two stage separation PT flash calculations are carried out twice; i.e., for the 1st stage and the 2nd stage (stock tank)
A liquid mixture (feed) of given overall composition either at or above its bubble point flashes in the 1st stage at a fixed P & T
The liquid phase in the 1st stage in turn becomes the feed for the 2nd stage, which flashes at atmospheric pressure and a given temperature
438

### Notes:

<!-- Slide number: 439 -->
Nomenclature used

![](Picture8.jpg)

![](Picture6.jpg)

nV2

nL2
nF lb moles
nV1

nL1
Well stream

![](Picture9.jpg)

![](Picture7.jpg)
439

### Notes:

<!-- Slide number: 440 -->
Equations for RSP, RST and R
lb-moles of separator gas per lb-mole of stock tank oil

![](Picture5.jpg)
one lb-mole of gas occupies 379.6 scf, and using the molecular weight and density of the stock tank oil

![](Picture10.jpg)
RSP =

![](Picture19.jpg)
RSP =
440

### Notes:

<!-- Slide number: 441 -->
Contd.
lb-moles of stock tank gas per lb-mole of stock tank oil

![](Picture5.jpg)

![](Picture8.jpg)

RST =

![](Picture19.jpg)
RST =
R = RSP + RST
441

### Notes:

<!-- Slide number: 442 -->
Equations for BoSb

![](Picture6.jpg)
BoSb =
Numerator

![](Picture9.jpg)

Denominator

![](Picture14.jpg)
442

### Notes:

<!-- Slide number: 443 -->

![](Picture6.jpg)
BoSb =
443

### Notes:

<!-- Slide number: 444 -->
Calculation steps
MWRO is calculated from feed (reservoir fluid) composition
Density of feed is (reservoir fluid) rRO is calculated from EOS
Flash calculations are carried out based on the feed composition and chosen P and T conditions for the first stage to yield       and
Liquid phase composition from first flash is used as feed for the stock tank flash to give       and
MWSTO is calculated from liquid phase composition from second flash
ST oil density, rSTO, is calculated from EOS liquid phase composition from second flash

![](Picture6.jpg)

![](Picture7.jpg)

![](Picture8.jpg)

![](Picture9.jpg)

444

### Notes:

<!-- Slide number: 445 -->
# Simulation of swelling tests
Given Zi and T

Calculate Pb, Zb

Assume ni = 1 and calculate Vsat = Zb (1) RT/Pb

Add injection gas. For e.g., if injection gas (ninj) in
total mixture is desired to be 5 mole %, then
ninj = 0.0526 moles and total moles nt = 1.0526

Or, simply

Calculate new Pbnew, Zbnew with Znew; Vsat new = Zbnew (1.0526) RT/Pbnew
Calculate swelling factor = Vsat new/Vsat

Add more injection gas, for e.g., 10 mole % and repeat the previous steps
New saturation pressures are generally compared with the reservoir pressure, which is a limiting pressure
445

### Notes:

<!-- Slide number: 446 -->
# Example of swelling test simulation
This is a real study for Al-Shaheen field (offshore) in Qatar
Reservoir temperature is 133oF
Reservoir oil was created using the recombined separator streams, and also numerically recombined
Experimental Swelling tests were conducted using the physically created injection gas; the TBP cuts of the dead oil were used along with other well defined components
Upto 50 mole% of injection gas was added to determine the swelling factor
| Components | Reservoir oil composition mole % | Injection gas composition mole % |
| --- | --- | --- |
| N2 | 0.46 | 2.37 |
| H2S | 0.01 | 0.00 |
| CO2 | 0.03 | 0.00 |
| C1 | 17.98 | 70.58 |
| C2 | 6.76 | 12.89 |
| C3 | 7.09 | 7.04 |
| IC4 | 2.00 | 1.34 |
| NC4 | 5.10 | 3.11 |
| IC5 | 2.99 | 1.08 |
| NC5 | 1.72 | 0.66 |
| C6 | 3.51 | 0.58 |
| C7+ | 52.36 | 0.35 |
|  | 100.00 | 100.00 |
446

### Notes:

<!-- Slide number: 447 -->
# Swelling calculations
| Psat, psia | Z | Vsat, ft3 | mole % inj. gas | nt | Swelling factor, bbl/bbl |
| --- | --- | --- | --- | --- | --- |
| 1060 | 0.5599 | 3.3597 | 0 | 1.000 | 1.000 |
| 1444 | 0.7072 | 3.4613 | 10 | 1.111 | 1.030 |
| 1896 | 0.8557 | 3.5880 | 20 | 1.250 | 1.068 |
| 2451 | 1.0108 | 3.7480 | 30 | 1.429 | 1.116 |
| 3177 | 1.1856 | 3.9566 | 40 | 1.667 | 1.178 |
| 4261 | 1.4181 | 4.2341 | 50 | 2.000 | 1.260 |
447

### Notes:

<!-- Slide number: 448 -->
# Swelling plots
448

### Notes:

<!-- Slide number: 449 -->
Composition based prediction models for IFT and viscosity
449

<!-- Slide number: 450 -->
Primary input is the vapor-liquid equilibrium or single phase (viscosity only) composition, densities from EOS
Also need critical properties, molecular weights, and parachor
Models have some theoretical foundation but often require some tuning/adjustments
Considered as industry standards – available in almost all PVT simulators
Seamless single phase to two phase or vice-versa transition is achieved in composition based viscosity modeling
450

### Notes:

<!-- Slide number: 451 -->
Parachor model for IFT prediction
Based on the original equations proposed by Macleod and Sugden for surface tension of pure components
Weinaug and Katz extended the pure component equation to mixtures by incorporating mixing rules

![](Picture1.jpg)
i = 1 to N components; x and y are mole fractions in the liquid and vapor phases; P is called the parachor (a constant for every component in the mixture).  is in dyne/cm (mN//m)

![](Picture4.jpg)
calculated by dividing the densities (in g/cm3) by the phase molecular weights

![](Picture2.jpg)

![](Picture9.jpg)
451

### Notes:

<!-- Slide number: 452 -->
Deviations of parachor method predicted IFTs for binary systems

![](Picture2.jpg)
For SCN, plus fractions:

![](Picture3.jpg)

![](Picture6.jpg)

![](Picture19.jpg)
Instead of a fixed value of 4 it can be varied by making
it a function of molar density differences. This improves
the prediction performance.
Main problem is with the parachor of the SCN and plus fractions.
This is often used as a tuning parameter.
452

### Notes:

<!-- Slide number: 453 -->
Parachor prediction for a synthetic
gas condensate mixture at 40oC
453

### Notes:

<!-- Slide number: 454 -->
Parachor prediction for a multiple
backward contact study at 100oC
Black oil and pure methane
454

### Notes:

<!-- Slide number: 455 -->
Composition based viscosity models
Lohrenz-Bray-Clark (LBC) and Pedersen and Fredenslund models – both adequately described in Pedersen et al. book – are based on the principle of corresponding states (properties expressed as reduced quantities) and have stood the test of time
Both are easily integrated into a PVT package, relatively easy to tune/calibrate, and a generally reasonable predictability for lighter oils or low viscosities
Main challenge is reliably predicting heavy oil viscosities and the effect of miscible solvents on viscosity reduction – important for Alaska

![](Picture4.jpg)
455

### Notes:

<!-- Slide number: 456 -->

![](Picture3.jpg)
The origin of LBC model
Jossi-Stiel-Thodos (AIChEJ, 1962)

![](Picture4.jpg)

![](Picture5.jpg)
r = /c
456

### Notes:

<!-- Slide number: 457 -->
LBC model for viscosity

![](Picture3.jpg)

rr = reduced density
a1 = 0.10230

a2 = 0.023364

a3 = 0.058533

a4 = –0.040758

a5 = 0.0093324

mo = low pressure viscosity

l = viscosity reducing parameter (or the inverse of critical viscosity)
Reduced viscosity = f(Reduced density)
Main problem is with the Vc (often used as a tuning parameter) of the plus fraction and very high sensitivity to density.
457

### Notes:

<!-- Slide number: 458 -->
Corresponding states model
– one reference
Fluid 1 is the given fluid (unknown)

Fluid 2 is the reference component (methane)

No density data is required

Viscosity of the reference component is necessary
458

### Notes:

<!-- Slide number: 459 -->
Corresponding states model

![](Picture2.jpg)
Subscript “o” is for reference component (methane). For heavy oils since Tc is very high the value of To at which methane viscosity is needed, becomes extremely low (solid phase) – can we even call it a corresponding states? Although Pedersen has recommended a correction for this.

![](Picture3.jpg)

![](Picture5.jpg)

![](Picture4.jpg)
459

### Notes:

<!-- Slide number: 460 -->
Prediction performance

![](Picture8.jpg)
460
Dandekar et al. – to be presented at the 2026 SPE IOR meeting

### Notes:

<!-- Slide number: 461 -->
Prediction performance

![](Picture6.jpg)
461
Dandekar et al. – to be presented at the 2026 SPE IOR meeting

### Notes:

<!-- Slide number: 462 -->
Seamless single phase to two phase or vice-versa transition
LBC prediction for a C1-nC4 binary system at 50.6oC
462

### Notes:

<!-- Slide number: 463 -->
# ADVANCED PHASE BEHAVIOR
463

<!-- Slide number: 464 -->
# What is PVT, phase behavior and fluid properties?
PVT – pressure volume temperature relationships for a reservoir fluid
Phase behavior – identification of the state in which these fluids exist in reservoirs; behavior of the phases as a function of pressure, temperature and composition
Fluid properties – determination of properties of the reservoir fluids (single phase, equilibrium phases) as a function of pressure, temperature, composition
464

<!-- Slide number: 465 -->
# Significance of PVT, phase behavior and reservoir fluid properties
State of existence
Determination of hydrocarbons in place
Reservoir simulation studies
Enhanced oil recovery processes
Design of surface processing facilities
465

<!-- Slide number: 466 -->
# State of existence
Well known states are liquids or gases, i.e., crude oils or natural gases
Wide ranges of pressure and temperature conditions and compositions exist in petroleum reservoirs; 15-20,000 psi and 60-350oF
Hydrocarbon systems in reservoirs display multiphase behavior – even upto three phases in some cases – over wide ranges of pressure and temperature
The conditions under which these phases exist in reservoirs, surface etc. itself is a matter of significant practical importance

466

<!-- Slide number: 467 -->
# Material balance equations
Oil material balance

![](Picture9.jpg)

Fluid properties

467

<!-- Slide number: 468 -->
# Material balance equations
Gas material balance

![](Picture6.jpg)

Fluid properties
468

<!-- Slide number: 469 -->
# Reservoir simulation
Which simulator to use, Black oil or Compositional?

y
,
y
,
y
...
y
1
2
3
n

x
,
x
,
x
...
x
1
2
3
n
Compositional

G

O
,
G
Black oil
469

<!-- Slide number: 470 -->
# Black oil simulation equations
Gas phase

Fluid properties
Oil phase

470

<!-- Slide number: 471 -->
# Compositional simulation model

Need EOS based Flash Calculations

Component balance, i = 1 to N
471

<!-- Slide number: 472 -->
# Recovery methods

![](Picture8.jpg)
Oil viscosity (reduction)?
Density? Asphaltene deposition?
Exchange of components?
Condensing/vaporizing drive?
472

<!-- Slide number: 473 -->
# Surface processes

![](Picture6.jpg)
Separator stream compositions,
densities, viscosities, volumes, moles, asphaltenes, waxes
473

<!-- Slide number: 474 -->
# How do we obtain this information?
Laboratory analysis of petroleum reservoir fluids on a collected sample
Conduct specific experimental studies to simulate the reservoir (in-situ), production, phase behavior related EOR (MMP, MME, slim tube, multiple contacts) tests at representative pressure and temperature conditions
Some laboratory experiments are needed to validate phase equilibrium simulations, rest are predicted thereafter
474

<!-- Slide number: 475 -->
Introduction to Petroleum
Reservoir Fluids
475

<!-- Slide number: 476 -->
# Preliminary introduction

![](Picture12.jpg)
Broadly petroleum reservoir fluids are fluids that exist
in a reservoir at a certain pressure and temperature
476
Amyx et. al.

<!-- Slide number: 477 -->
# Petroleum chemistry
Organic Chemistry
Basically, the study of hydrocarbons or two elements, i.e., Hydrogen and Carbon
477

<!-- Slide number: 478 -->
# Paraffins (also called as alkanes)
General formula – CnH2n+2
Also called as saturated – C atoms are attached to as many H atoms as possible, i.e., C atoms are saturated with H through single bonds

e.g. Methane (CH4), Ethane (C2H6), Propane (C3H8)

![http://progdev.sait.ab.ca/OGPA210/Modules/module3/ch4.gif](Picture8.jpg)

![http://progdev.sait.ab.ca/OGPA210/Modules/module3/c2h8.gif](Picture10.jpg)
Methane
Ethane
478

<!-- Slide number: 479 -->
# Isomers of alkanes
Same molecular formula but different arrangement of atoms – molecular weight remains same but physical properties differ (n-butane and i-butane Tc and Pc are 305.56°F, 550.56 psia and 274.39°F and 526.34 psia).

Number of isomers increase with carbon number; C18 has 60, 523 isomers!

![](Picture4.jpg)
479

<!-- Slide number: 480 -->
# Common normal alkanes

![](Picture141.jpg)
480

<!-- Slide number: 481 -->
# Alkenes and Alkynes
Alkenes are also called as olefins; ethylene and propylene are common examples
Alkenes have a general formula CnH2n
Alkenes are rarely found in naturally occurring hydrocarbons
Ethylene is the starting material for polyethylene which is found in a variety of commercial products including milk bottles and plastic bags
481

<!-- Slide number: 482 -->
# Contd.
The general formula for alkynes is CnH2n-2
Common examples of alkynes include substances such as acetylene and propyne
Rarely found in naturally occurring hydrocarbons
482

<!-- Slide number: 483 -->
# Cycloaliphatics
Cycloalkanes or cycloparaffins are commonly known in the petroleum industry as naphthenes
General formula is given by CnH2n
Carbon atoms are arranged in rings instead of chains as seen in the case of normal alkanes

![](Picture4.jpg)
483

<!-- Slide number: 484 -->
# Aromatics
Also called as arenes
Many compounds belonging to this class have very pleasant odors that is why the name aromatics
Generally very toxic, and some are carcinogenic in nature
Common examples are benzene, toluene, xylene

![http://progdev.sait.ab.ca/OGPA210/Modules/module5/1504a.gif](Picture4.jpg)
484

<!-- Slide number: 485 -->
# Non-hydrocarbons and metals
Most common: CO2,N2,H2S
Nitrogen, Oxygen and Sulfur* form part of heavy molecules present in the oil (resins and asphaltenes)
Sulfur compounds poison catalysts used in refinery operations
N2 and CO2 responsible for formation of acidic solution in the presence of water
Heavy metals : Ni, Va, Pb, Cd
* Even though H2S may not explicitly show up in an oil composition, the sulfur is present this way making the oil sour.
485

<!-- Slide number: 486 -->
# Nasty solid components originating from oil, gas, formation water

![](Picture5.jpg)

![](Picture3.jpg)

![](Picture5.jpg)

![](Picture5.jpg)

![](Picture2.jpg)
486

<!-- Slide number: 487 -->
# Classification of petroleum
Petroleum reservoir fluids are broadly
classified according to the following –

Chemical classification
Physical classification
Classification of reservoir gases is relatively easy as they contain fewer (lighter) hydrocarbons; identified by analytical techniques such as Gas Chromatography.  Specific gravity of gases is used as indicator for the physical classification
487

<!-- Slide number: 488 -->
# Reservoir oils
Considering the wide range of chemical components present in oils, the chemical classification mainly consists of average chemical analysis known as PIANO analysis
PIANO = Paraffins-Isoparaffins-Aromatics-Naphthenes-Olefins
Considering the rarity of olefins and lumping of all the paraffins – the analysis is reduced to simply PNA
488

<!-- Slide number: 489 -->
# Physical classification of reservoir oils
Classified according to various physical properties such as specific gravity, color, sulfur content, refractive index, odor, and viscosity
However, these physical properties is in fact a result of the PNA distribution of a given oil
Commercial value of a crude oil, to a great extent, is determined by its specific gravity or usually by the API gravity
489

<!-- Slide number: 490 -->
Oil gravities
go =

![](Picture4.jpg)
oAPI =
go = specific gravity of oil, dimensionless

ro = density of oil at standard pressure and temperature (14.7 psi and 60oF)

rw = density of water at standard pressure and temperature (14.7 psi and 60oF) = ~1 g/cm3 = 1000 kg/m3 = 62.43 lbm/ft3
490

<!-- Slide number: 491 -->
Gas gravity

![](Picture6.jpg)

![](Picture9.jpg)
Standard P & T
MWair  28.97
 0.79*28+0.21*32+Ar, CO2 etc.
491

<!-- Slide number: 492 -->
# The Five Petroleum Reservoir Fluids
From a PVT, phase behavior perspective, reservoir fluids are classified as –

 	Black Oils
 	Volatile Oils
 	Gas Condensates
 	Wet Gases
 	Dry Gases

492

<!-- Slide number: 493 -->
# Basic characteristics of the five reservoir fluids

![](Picture82.jpg)
493

<!-- Slide number: 494 -->
Typical Reservoir Fluid Compositions

![](Picture1.jpg)
Riazi, 2005
494

<!-- Slide number: 495 -->
# Compositional Distribution of Reservoir Fluids

![](Picture7.jpg)
495

<!-- Slide number: 496 -->
# Formation waters
Also known as oilfield water, reservoir water, connate water, or simply brine
Common solids present in water are sodium chloride, calcium chloride, potassium chloride, magnesium chloride
Formation waters are chemically characterized by their salinities
From physical characterization point of view; density and viscosity are important properties
496

<!-- Slide number: 497 -->
# Formation water compositions

![](Picture2.jpg)
Extensive pure water database exists, which is used to determine formation water properties by applying the salinity correction factor through empirical correlations
Whitson & Brulé, 2000
497

<!-- Slide number: 498 -->
# Formation water density and viscosity

![](Picture1.jpg)

![](Picture2.jpg)
 and η are density and viscosity in g/cm3 and cP; subscripts s and w are for salt and pure water; T and P are temperature and pressure in oF and psia; Cs is the salt concentration in weight %.
498
Empirical correlations of Numbere (1977) in Pedersen et al. (2015)